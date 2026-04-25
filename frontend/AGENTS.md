<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Application Architecture (local dev)

This project implements a three-layer architecture described below. The frontend (Next.js) proxies requests to a lightweight Flask backend which in turn talks to an agent layer. For local development a mock Agentverse server is included so you can test the full flow without registering agents.

## Local dev quickstart

1. Start the mock agents server (simulates Agentverse):

   cd ../backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python agent_mock_server.py

2. In another terminal, start Flask:

   source venv/bin/activate
   python app.py

3. Start the Next.js frontend:

   cd ../frontend
   npm install
   npm run dev

4. Use the frontend or call the proxy routes directly:

   POST http://localhost:3000/api/intake
   POST http://localhost:3000/api/eligibility
   POST http://localhost:3000/api/apply


## Architecture notes

- The Next.js API routes in `app/api/*` are thin proxies to Flask so the Flask URL never appears in the browser. This avoids CORS in production.
- The Flask app in `/backend/app.py` is intentionally thin: it validates requests and forwards them to the agent layer (mock at `http://127.0.0.1:5100` in dev).
- Replace `agent_mock_server.py` with real Fetch.ai uAgents processes and update `AGENTVERSE_URL` in `.env` when you're ready to integrate with Agentverse.
