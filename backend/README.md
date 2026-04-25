Local backend for benefits_nav

Quickstart:

1. Create a virtualenv and install deps

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

2. Copy .env.example to .env and edit if needed

cp .env.example .env

3. Start the mock agent server (simulates Agentverse)

python agent_mock_server.py

4. In another terminal, start Flask

python app.py

The frontend proxies call to Flask at http://127.0.0.1:5000
