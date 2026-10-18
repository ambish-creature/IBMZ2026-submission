# Social Media Fact-Checker

A Python and FastAPI prototype for assessing claims submitted from social media text.

## Features
- Extracts candidate claims using simple rules.
- Matches claims against manually reviewed evidence in SQLite.
- Returns verdicts and supporting explanations for matching evidence.
- Returns unverified when local evidence is unavailable.
- Retrieves Wikipedia search results as research leads.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python database.py
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

## Endpoints
- GET / — API information
- GET /health — health check
- POST /evidence — save evidence
- POST /fact-check — assess submitted text

## Limitations
This is a prototype. Verdicts depend on manually entered evidence. Wikipedia results are research leads, not independently verified verdicts. Claim extraction and evidence matching use simple rules.

## Privacy
The local evidence database and backups should not be committed. Never commit secrets or private credentials.
