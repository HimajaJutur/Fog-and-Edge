import json
import boto3
import os
import time
from datetime import datetime
from decimal import Decimal

# ─────────────────────────────────────────
# AWS CLIENTS
# ─────────────────────────────────────────
dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.environ.get("AWS_REGION", "us-east-1")
)

table = dynamodb.Table(
    os.environ.get("DYNAMODB_TABLE", "ThermalMonitorData")
)

COOLDOWN_TABLE_NAME = os.environ.get("COOLDOWN_TABLE", "ThermalAlertCooldown")
try:
    cooldown_table = dynamodb.Table(COOLDOWN_TABLE_NAME)
except Exception:
    cooldown_table = None

sns_client = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
# Hardcoded SNS Topic ARN
TOPIC_ARN = "arn:aws:sns:us-east-1:344902008408:DataCenterAlerts"
print(f"[SNS] Topic ARN loaded: {TOPIC_ARN}")

SNS_COOLDOWN_SECONDS = int(os.environ.get("SNS_COOLDOWN_SECONDS", "60"))


# ─────────────────────────────────────────
# RESPONSE HELPERS
# ─────────────────────────────────────────
HEADERS = {
    "Content-Type":                "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def ok(body):
    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(body)}

def error(code, msg):
    return {"statusCode": code, "headers": HEADERS, "body": json.dumps({"error": msg})}


# ─────────────────────────────────────────
# FLOAT → DECIMAL  (DynamoDB requirement)
# ─────────────────────────────────────────
def floats_to_decimal(obj):
    if isinstance(obj, list):
        return [floats_to_decimal(i) for i in obj]
    if isinstance(obj, dict):
        return {k: floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, float):
        return Decimal(str(round(obj, 4)))
    return obj


# ─────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────
REQUIRED_FIELDS = [
    "sensor_id", "timestamp", "temperature", "humidity",
    "airflow", "cpu_load", "heat_index", "status"
]

def validate(payload):
    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    if payload["status"] not in ("NORMAL", "WARNING", "CRITICAL"):
        raise ValueError(f"Invalid status value: '{payload['status']}' — must be NORMAL, WARNING, or CRITICAL")


# ─────────────────────────────────────────
# SNS COOLDOWN
# ─────────────────────────────────────────
def is_in_cooldown(sensor_id: str) -> bool:
    if cooldown_table is None:
        return False
    try:
        resp = cooldown_table.get_item(Key={"alert_key": f"sns_cooldown_{sensor_id}"})
        item = resp.get("Item")
        if not item:
            return False
        expires_at = float(item.get("expires_at", 0))
        return time.time() < expires_at
    except Exception as e:
        print(f"[COOLDOWN] Could not check cooldown table: {e}")
        return False


def set_cooldown(sensor_id: str):
    if cooldown_table is None:
        return
    try:
        expires_at = int(time.time()) + SNS_COOLDOWN_SECONDS
        cooldown_table.put_item(Item={
            "alert_key":  f"sns_cooldown_{sensor_id}",
            "expires_at": expires_at,
        })
        print(f"[COOLDOWN] Set {SNS_COOLDOWN_SECONDS}s cooldown for sensor {sensor_id}")
    except Exception as e:
        print(f"[COOLDOWN] Could not write cooldown: {e}")


# ─────────────────────────────────────────
# SNS ALERT
# ─────────────────────────────────────────
def send_sns_alert(payload: dict):
    sensor_id = payload.get("sensor_id", "UNKNOWN")

    if is_in_cooldown(sensor_id):
        print(f"[SNS] SKIPPED: Cooldown active for sensor {sensor_id} ({SNS_COOLDOWN_SECONDS}s window)")
        return

    alerts_text = "\n".join(payload.get("alerts", [])) or "No detail available"

    message = f"""
CRITICAL DATA CENTER ALERT
==========================
Sensor ID   : {payload.get('sensor_id')}
Timestamp   : {payload.get('timestamp')}
Temperature : {payload.get('temperature')} °C
Humidity    : {payload.get('humidity')} %
Airflow     : {payload.get('airflow')} %
CPU Load    : {payload.get('cpu_load')} %
Heat Index  : {payload.get('heat_index')} °C
Status      : {payload.get('status')}

Alerts:
{alerts_text}

Immediate attention required!
"""

    try:
        response = sns_client.publish(
            TopicArn=TOPIC_ARN,
            Subject="CRITICAL ALERT - Data Center Thermal Monitor",
            Message=message,
        )
        message_id = response.get("MessageId", "unknown")
        print(f"[SNS] Alert sent successfully. MessageId: {message_id}")
        set_cooldown(sensor_id)

    except sns_client.exceptions.AuthorizationErrorException:
        print("[SNS] ERROR: IAM role does not have sns:Publish permission.")
        print("[SNS] Fix: Add 'sns:Publish' to the Lambda execution role in IAM.")

    except sns_client.exceptions.NotFoundException:
        print(f"[SNS] ERROR: Topic not found — ARN may be wrong: {TOPIC_ARN}")

    except Exception as e:
        print(f"[SNS] ERROR: Unexpected failure — {type(e).__name__}: {e}")


# ─────────────────────────────────────────
# LAMBDA HANDLER
# ─────────────────────────────────────────
def lambda_handler(event, context):

    print(f"[Lambda] Received event: {json.dumps(event)[:300]}")

    if event.get("httpMethod") == "OPTIONS":
        return ok({"message": "CORS OK"})

    try:
        body = event.get("body", "{}")
        payload = json.loads(body) if isinstance(body, str) else body
        if not isinstance(payload, dict):
            return error(400, "Request body must be a JSON object")
    except json.JSONDecodeError as e:
        print(f"[Lambda] JSON parse error: {e}")
        return error(400, f"Invalid JSON: {e}")

    try:
        validate(payload)
    except ValueError as e:
        print(f"[Lambda] Validation failed: {e}")
        return error(400, str(e))

    payload["lambda_timestamp"] = datetime.utcnow().isoformat() + "Z"

    item = floats_to_decimal(payload)

    try:
        table.put_item(Item=item)
        print(f"[DynamoDB] Stored reading for sensor {payload.get('sensor_id')} | status={payload.get('status')}")
    except Exception as e:
        print(f"[DynamoDB] ERROR: {e}")
        return error(500, f"DynamoDB error: {str(e)}")

    if payload["status"] == "CRITICAL":
        print(f"[Lambda] CRITICAL status detected — attempting SNS alert")
        send_sns_alert(payload)
    else:
        print(f"[Lambda] Status is {payload['status']} — no SNS alert needed")

    return ok({
        "message":   "Stored successfully",
        "sensor_id": payload["sensor_id"],
        "status":    payload["status"],
        "lambda_timestamp": payload["lambda_timestamp"],
    })