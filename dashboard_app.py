
from flask import Flask, render_template, jsonify
import requests
import os

app = Flask(__name__)

FOG_NODE_URL = os.environ.get("FOG_NODE_URL", "http://127.0.0.1:5000")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/data")
def data():
    try:
        resp = requests.get(f"{FOG_NODE_URL}/dashboard-data", timeout=4)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error":     "Cannot reach Fog Node — is fog_node.py running?",
            "history":   [],
            "latest":    {},
            "fog_stats": {},
        }), 503
    except Exception as e:
        return jsonify({
            "error":     str(e),
            "history":   [],
            "latest":    {},
            "fog_stats": {},
        }), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "dashboard"}), 200


if __name__ == "__main__":
    print("=" * 55)
    print("  DASHBOARD — Data Center Thermal Monitor")
    print(f"  Fog Node: {FOG_NODE_URL}")
    print("  Open browser: http://localhost:8080")
    print("=" * 55)
    app.run(host="0.0.0.0", port=8080, debug=True)