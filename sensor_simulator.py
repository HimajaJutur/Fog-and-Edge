"""
sensor_simulator.py
Fog-Based Data Center Thermal Monitoring System
Simulates 5 sensors: Temperature, Humidity, Airflow, CPU Load, Heat Index
Sends data to the Fog Node every SEND_INTERVAL seconds.
"""

import requests
import random
import time
import math
import json
import argparse
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
FOG_NODE_URL  = "http://127.0.0.1:5000/sensor-data"   # Fog Node endpoint
SEND_INTERVAL = 30                                       # Seconds between readings
SENSOR_ID     = "RACK-01"                              # Logical sensor/rack ID

# ─────────────────────────────────────────
# HEAT INDEX FORMULA  (Rothfusz, NWS)
# Valid when temp > 27 °C and humidity > 40 %
# ─────────────────────────────────────────
def calculate_heat_index(temp_c: float, humidity: float) -> float:
    """Return Heat Index in °C using the NWS Rothfusz regression."""
    T = temp_c * 9 / 5 + 32          # convert to °F for the formula
    RH = humidity

    HI = (-42.379
          + 2.04901523 * T
          + 10.14333127 * RH
          - 0.22475541 * T * RH
          - 0.00683783 * T * T
          - 0.05481717 * RH * RH
          + 0.00122874 * T * T * RH
          + 0.00085282 * T * RH * RH
          - 0.00000199 * T * T * RH * RH)

    HI_c = (HI - 32) * 5 / 9        # back to °C
    return round(HI_c, 2)


# ─────────────────────────────────────────
# ANOMALY DETECTION (basic)
# ─────────────────────────────────────────
def is_valid_reading(temp, humidity, airflow, cpu_load) -> bool:
    """Discard obviously faulty sensor values before sending."""
    if temp <= 0 or temp > 150:
        return False
    if humidity < 1 or humidity > 100:
        return False
    if airflow < 0 or airflow > 100:
        return False
    if cpu_load < 0 or cpu_load > 100:
        return False
    return True


# ─────────────────────────────────────────
# SENSOR READING GENERATOR
# ─────────────────────────────────────────
def generate_sensor_data(scenario: str = "normal"):
    """
    Generate a realistic sensor reading.
    scenario: 'normal' | 'warning' | 'critical' | 'random'
    """
    if scenario == "normal":
        temp     = round(random.uniform(40, 69), 2)
        humidity = round(random.uniform(30, 55), 2)
        airflow  = round(random.uniform(60, 100), 2)
        cpu_load = round(random.uniform(10, 60), 2)

    elif scenario == "warning":
        temp     = round(random.uniform(70, 80), 2)
        humidity = round(random.uniform(40, 65), 2)
        airflow  = round(random.uniform(40, 70), 2)
        cpu_load = round(random.uniform(60, 85), 2)

    elif scenario == "critical":
        temp     = round(random.uniform(81, 110), 2)
        humidity = round(random.uniform(55, 85), 2)
        airflow  = round(random.uniform(0, 39), 2)
        cpu_load = round(random.uniform(80, 100), 2)

    else:  # random mix
        temp     = round(random.uniform(35, 110), 2)
        humidity = round(random.uniform(20, 90), 2)
        airflow  = round(random.uniform(0, 100), 2)
        cpu_load = round(random.uniform(5, 100), 2)

    # Occasionally inject a faulty spike to test anomaly filter
    if random.random() < 0.05:
        temp = 0   # faulty zero reading

    if not is_valid_reading(temp, humidity, airflow, cpu_load):
        print("[SENSOR] ⚠  Faulty reading detected — discarded (anomaly filter).")
        return None

    heat_index = calculate_heat_index(temp, humidity)

    return {
        "sensor_id": SENSOR_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "temperature": temp,       # °C
        "humidity": humidity,      # %
        "airflow": airflow,        # % of max fan speed
        "cpu_load": cpu_load,      # %
        "heat_index": heat_index,  # °C  (derived)
    }


# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────
def run(scenario: str, interval: int):
    print(f"[SENSOR] Starting sensor simulator → {FOG_NODE_URL}")
    print(f"[SENSOR] Scenario: {scenario.upper()}  |  Interval: {interval}s")
    print("-" * 55)

    while True:
        data = generate_sensor_data(scenario)

        if data is None:
            time.sleep(interval)
            continue

        print(f"[SENSOR] Sending → Temp={data['temperature']}°C  "
              f"Hum={data['humidity']}%  "
              f"Airflow={data['airflow']}%  "
              f"CPU={data['cpu_load']}%  "
              f"HI={data['heat_index']}°C")

        try:
            response = requests.post(FOG_NODE_URL, json=data, timeout=5)
            result   = response.json()
            status   = result.get("status", "?")
            print(f"[SENSOR] ✓ Fog Node responded → STATUS: {status}\n")
        except requests.exceptions.ConnectionError:
            print("[SENSOR] ✗ Could not reach Fog Node. Is it running?\n")
        except Exception as e:
            print(f"[SENSOR] ✗ Error: {e}\n")

        time.sleep(interval)


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Center Sensor Simulator")
    parser.add_argument(
        "--scenario",
        choices=["normal", "warning", "critical", "random"],
        default="random",
        help="Simulation scenario (default: random)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=SEND_INTERVAL,
        help=f"Send interval in seconds (default: {SEND_INTERVAL})",
    )
    args = parser.parse_args()
    run(args.scenario, args.interval)
