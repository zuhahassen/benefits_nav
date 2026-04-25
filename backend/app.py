from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

AGENTVERSE_URL = os.getenv("AGENTVERGE_URL", "http://localhost:5100")
ASI1_MINI_URL = os.getenv("ASI1_MINI_URL")


@app.route("/api/intake", methods=["POST"])
def intake():
    payload = request.json or {}
    # Basic validation
    required = ["household_size", "state", "monthly_income"]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400

    # Proxy to orchestrator agent in Agentverse (mock)
    try:
        resp = requests.post(f"{AGENTVERSE_URL}/orchestrator/intake", json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": "failed to talk to agents", "detail": str(e)}), 502

    return jsonify(resp.json())


@app.route("/api/eligibility", methods=["POST"])
def eligibility():
    payload = request.json or {}
    try:
        resp = requests.post(f"{AGENTVERSE_URL}/eligibility/check", json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": "failed to talk to agents", "detail": str(e)}), 502

    return jsonify(resp.json())


@app.route("/api/apply", methods=["POST"])
def apply():
    payload = request.json or {}
    try:
        resp = requests.post(f"{AGENTVERSE_URL}/application/start", json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": "failed to talk to agents", "detail": str(e)}), 502

    return jsonify(resp.json())


@app.route("/api/asi1/reason", methods=["POST"])
def asi1_reason():
    payload = request.json or {}
    if not ASI1_MINI_URL:
        return jsonify({"error": "ASI-1 Mini URL not configured"}), 500

    try:
        resp = requests.post(ASI1_MINI_URL, json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": "ASI-1 Mini call failed", "detail": str(e)}), 502

    return jsonify(resp.json())


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host=host, port=port, debug=True)
