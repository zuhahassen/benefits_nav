"""
A tiny mock Agentverse-like HTTP server to simulate agent endpoints locally.
This keeps things simple for local development: Next.js -> Flask -> agent_mock_server

Endpoints:
- POST /orchestrator/intake
- POST /eligibility/check
- POST /application/start

This is not uAgents; it's a quick stand-in you can replace with real agents later.
"""

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/orchestrator/intake", methods=["POST"])
def orchestrator_intake():
    profile = request.json or {}
    # In a real system this would create a session and trigger ProfileAgent
    return jsonify({"session_id": "sess_mock_123", "status": "orchestrated", "profile": profile})


@app.route("/eligibility/check", methods=["POST"])
def eligibility_check():
    profile = request.json or {}
    # Simple rule-based mock: if monthly_income < 2000 => likely for SNAP
    results = []
    income = profile.get("monthly_income", 999999)
    household = profile.get("household_size", 1)

    if income < 2000:
        results.append({"benefit": "SNAP", "verdict": "likely", "explanation": "income below local threshold"})
    elif income < 4000:
        results.append({"benefit": "SNAP", "verdict": "possible", "explanation": "income near threshold"})
    else:
        results.append({"benefit": "SNAP", "verdict": "ineligible", "explanation": "income too high"})

    # Add a second mock benefit
    results.append({"benefit": "WIC", "verdict": "possible", "explanation": "age/children check needed"})

    return jsonify({"session_id": "sess_mock_123", "results": results})


@app.route("/application/start", methods=["POST"])
def application_start():
    data = request.json or {}
    benefit = data.get("benefit", "unknown")
    profile = data.get("profile", {})

    guidance = {
        "benefit": benefit,
        "steps": [
            "Gather ID and proof of address",
            "Collect income documents",
            "Fill out online form at example.gov",
            "Submit and wait 4-6 weeks"
        ],
        "where_to_apply": "https://example.gov/apply",
        "documents": ["ID", "proof_of_address", "paystubs"]
    }

    return jsonify({"session_id": "sess_mock_123", "guidance": guidance})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100, debug=True)
