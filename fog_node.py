"""
fog_node.py
Fog-Based Data Center Thermal Monitoring System
─────────────────────────────────────────────────
Fog Node  —  runs locally (Raspberry Pi / edge server / laptop)

Responsibilities:
  1. Receive raw sensor data via HTTP POST /sensor-data
  2. Process & classify: NORMAL / WARNING / CRITICAL
  3. Filter out redundant readings (edge intelligence)
  4. Forward meaningful data to AWS API Gateway
  5. Serve the /dashboard endpoint (used by dashboard app)
  6. Expose /stats for fog reduction metrics
"""

from flask import Flask, request, jsonify
from datetime import datetime
import requests
import math
import os
import json

app = Flask(__name__)

# ─────────────────────────────────────────
# CONFIGURATION  — edit these values
# ─────────────────────────────────────────
AWS_API_GATEWAY_URL = os.environ.get(
    "AWS_API_GATEWAY_URL",
    "https://gq0m70twc3.execute-api.us-east-1.amazonaws.com/prod/data"
)

# Thresholds
TEMP_CRITICAL  = 80    # °C
TEMP_WARNING   = 70    # °C
AIRFLOW_LOW    = 40    # %  — below this = "low airflow"

# ─────────────────────────────────────────
# IN-MEMORY STORE  (last 50 readings)
# ─────────────────────────────────────────
MAX_HISTORY   = 50
data_history  = []     # processed readings for dashboard
fog_stats     = {
    "total_received":  0,
    "total_forwarded": 0,
    "total_filtered":  0,
    "critical_alerts": 0,
}
last_forwarded = None   # used for duplicate filter


# ─────────────────────────────────────────
# PROCESSING LOGIC
# ─────────────────────────────────────────
def classify_status(temp: float, airflow: float) -> str:
    """Return NORMAL / WARNING / CRITICAL based on sensor values."""
    if temp > TEMP_CRITICAL and airflow < AIRFLOW_LOW:
        return "CRITICAL"
    if temp > TEMP_CRITICAL:
        return "CRITICAL"
    if temp > TEMP_WARNING:
        return "WARNING"
    return "NORMAL"


def generate_alerts(status: str, temp: float, airflow: float,
                    humidity: float, cpu_load: float) -> list[str]:
    """Return human-readable alert strings for the given reading."""
    alerts = []
    if status == "CRITICAL":
        alerts.append(f"🔴 CRITICAL: Temperature {temp}°C exceeds safe limit (>{TEMP_CRITICAL}°C)")
        if airflow < AIRFLOW_LOW:
            alerts.append(f"🔴 CRITICAL: Low airflow detected ({airflow}%) — cooling failure risk!")
    elif status == "WARNING":
        alerts.append(f"🟡 WARNING: Temperature {temp}°C approaching critical threshold")
    if humidity > 70:
        alerts.append(f"⚠  High humidity ({humidity}%) — condensation risk")
    if cpu_load > 90:
        alerts.append(f"⚠  CPU Load very high ({cpu_load}%)")
    return alerts


def should_forward(processed: dict, status: str) -> bool:
    """
    Edge intelligence: decide whether to forward to cloud.
    Skip if the status is NORMAL and the reading is very similar
    to the last forwarded one (reduces cloud traffic by ~60 %).
    """
    global last_forwarded

    # Always forward WARNING / CRITICAL
    if status != "NORMAL":
        return True

    # Forward if no previous reading
    if last_forwarded is None:
        return True

    # Forward if temperature changed by more than 3 °C
    delta_temp = abs(processed["temperature"] - last_forwarded.get("temperature", 0))
    if delta_temp > 3:
        return True

    # Otherwise skip — fog filtering in action
    return False


# ─────────────────────────────────────────
# ROUTE: receive sensor data
# ─────────────────────────────────────────
@app.route("/sensor-data", methods=["POST"])
def receive_sensor_data():
    global last_forwarded

    raw = request.get_json(force=True)
    if not raw:
        return jsonify({"error": "No JSON body"}), 400

    fog_stats["total_received"] += 1

    # Extract fields
    temp      = raw.get("temperature", 0)
    humidity  = raw.get("humidity", 0)
    airflow   = raw.get("airflow", 0)
    cpu_load  = raw.get("cpu_load", 0)
    heat_idx  = raw.get("heat_index", 0)
    sensor_id = raw.get("sensor_id", "UNKNOWN")
    timestamp = raw.get("timestamp", datetime.utcnow().isoformat() + "Z")

    # Classify
    status = classify_status(temp, airflow)
    alerts = generate_alerts(status, temp, airflow, humidity, cpu_load)

    if status == "CRITICAL":
        fog_stats["critical_alerts"] += 1

    # Build processed payload
    processed = {
        "sensor_id":   sensor_id,
        "timestamp":   timestamp,
        "fog_timestamp": datetime.utcnow().isoformat() + "Z",
        "temperature": temp,
        "humidity":    humidity,
        "airflow":     airflow,
        "cpu_load":    cpu_load,
        "heat_index":  heat_idx,
        "status":      status,
        "alerts":      alerts,
    }

    # Store in history (for dashboard)
    data_history.append(processed)
    if len(data_history) > MAX_HISTORY:
        data_history.pop(0)

    # Decide whether to forward
    forward = should_forward(processed, status)

    if forward:
        fog_stats["total_forwarded"] += 1
        last_forwarded = processed
        cloud_result = forward_to_cloud(processed)
        processed["cloud_forwarded"] = True
        processed["cloud_response"]  = cloud_result
        print(f"[FOG] ✓ Forwarded to cloud | STATUS={status} | Temp={temp}°C")
    else:
        fog_stats["total_filtered"] += 1
        processed["cloud_forwarded"] = False
        print(f"[FOG] ⊘ Filtered (NORMAL, minimal change) | Temp={temp}°C")

    return jsonify({
        "status":          status,
        "alerts":          alerts,
        "cloud_forwarded": forward,
        "fog_stats":       fog_stats,
    }), 200


# ─────────────────────────────────────────
# FORWARD TO AWS
# ─────────────────────────────────────────
def forward_to_cloud(payload: dict) -> dict:
    """Send processed data to AWS API Gateway. Returns response or error info."""
    try:
        resp = requests.post(
            AWS_API_GATEWAY_URL,
            json=payload,
            timeout=8,
            headers={"Content-Type": "application/json"},
        )
        return {"http_status": resp.status_code, "body": resp.text[:200]}
    except requests.exceptions.ConnectionError:
        print("[FOG] ✗ Cannot reach AWS — check AWS_API_GATEWAY_URL")
        return {"error": "connection_error"}
    except Exception as e:
        print(f"[FOG] ✗ Cloud forward error: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────
# ROUTE: dashboard data (latest readings)
# ─────────────────────────────────────────
@app.route("/dashboard-data", methods=["GET"])
def dashboard_data():
    return jsonify({
        "history":  data_history[-20:],   # last 20 for chart
        "latest":   data_history[-1] if data_history else {},
        "fog_stats": fog_stats,
    })


# ─────────────────────────────────────────
# ROUTE: fog stats
# ─────────────────────────────────────────
@app.route("/stats", methods=["GET"])
def stats():
    total = fog_stats["total_received"]
    reduction = (
        round(fog_stats["total_filtered"] / total * 100, 1) if total else 0
    )
    return jsonify({**fog_stats, "reduction_percent": reduction})


# ─────────────────────────────────────────
# ROUTE: health check
# ─────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "fog_node"}), 200


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  FOG NODE — Data Center Thermal Monitor")
    print(f"  Cloud endpoint: {AWS_API_GATEWAY_URL}")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=True)
