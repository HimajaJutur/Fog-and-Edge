"""
lambda_function.py
AWS Lambda Handler — Fog-Based Data Center Thermal Monitoring System
SNS SAFE VERSION (Learner Lab Compatible)
"""

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

sns = boto3.client("sns")

# If not set → SNS will be skipped safely
TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", None)

# ─────────────────────────────────────────
# GLOBAL (anti-spam)
# ─────────────────────────────────────────
last_alert_time = 0

# ─────────────────────────────────────────
# FLOAT → DECIMAL
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
# RESPONSE HELPERS
# ─────────────────────────────────────────
HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def ok(body):
    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(body)}

def error(code, msg):
    return {"statusCode": code, "headers": HEADERS, "body": json.dumps({"error": msg})}


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
        raise ValueError(f"Missing fields: {missing}")

    if payload["status"] not in ("NORMAL", "WARNING", "CRITICAL"):
        raise ValueError(f"Invalid status: {payload['status']}")


# ─────────────────────────────────────────
# SNS ALERT FUNCTION (SAFE 🚨)
# ─────────────────────────────────────────
def send_sns_alert(payload):
    global last_alert_time

    # If SNS not configured → skip silently
    if not TOPIC_ARN:
        print("[SNS] No TOPIC_ARN configured → skipping")
        return

    current_time = time.time()

    # Anti-spam (1 alert / 60 sec)
    if current_time - last_alert_time < 60:
        print("[SNS] Skipping alert (cooldown)")
        return

    try:
        message = f"""
🚨 CRITICAL DATA CENTER ALERT 🚨

Sensor ID: {payload['sensor_id']}
Temperature: {payload['temperature']} °C
Humidity: {payload['humidity']} %
Airflow: {payload['airflow']}
CPU Load: {payload['cpu_load']} %
Heat Index: {payload['heat_index']}

Status: {payload['status']}

⚠ Immediate attention required!
"""

        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="🚨 CRITICAL ALERT - Data Center",
            Message=message
        )

        last_alert_time = current_time
        print("[SNS] Alert sent successfully")

    except Exception as e:
        # Learner Lab case → no permission
        print("[SNS ERROR - likely IAM restriction]", str(e))


# ─────────────────────────────────────────
# LAMBDA HANDLER
# ─────────────────────────────────────────
def lambda_handler(event, context):

    print(f"[Lambda] Event: {json.dumps(event)[:300]}")

    # CORS
    if event.get("httpMethod") == "OPTIONS":
        return ok({"message": "CORS OK"})

    # Parse body
    try:
        body = event.get("body", "{}")
        payload = json.loads(body) if isinstance(body, str) else body
    except Exception:
        return error(400, "Invalid JSON")

    # Validate
    try:
        validate(payload)
    except ValueError as e:
        return error(400, str(e))

    # Add timestamp
    payload["lambda_timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Convert floats
    item = floats_to_decimal(payload)

    # Store in DynamoDB
    try:
        table.put_item(Item=item)
        print("[DynamoDB] Stored successfully")
    except Exception as e:
        return error(500, f"DynamoDB error: {str(e)}")

    # 🚨 SNS TRIGGER (SAFE)
    if payload["status"] == "CRITICAL":
        send_sns_alert(payload)

    return ok({
        "message": "Stored successfully",
        "sensor_id": payload["sensor_id"],
        "status": payload["status"]
    })