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
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e), "history": [], "latest": {}, "fog_stats": {}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)