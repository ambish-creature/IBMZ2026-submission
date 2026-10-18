# ============================================================
# File: app.py
# Purpose: Local fact-checker API connected to SQLite.
# No external APIs or AI model are used in this version.
# ============================================================

import re
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests 
from html import unescape
# from external_search import search_wikipedia

# fix 
BASE_URL = "https" + "://" + "en.wikipedia.org"
WIKIPEDIA_API = BASE_URL + "/w/api.php"

# fix imports (temporary) 
def clean_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    text = re.sub(r"<[^>]*>", "", text)
    return unescape(text).strip()

def search_wikipedia(query: str, limit: int = 5) -> list[dict]:
    """Return potentially relevant Wikipedia articles."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": limit,
    }
    headers = {
        "User-Agent": "SocialMediaFactChecker/0.1 (hackathon prototype)"
    }

    try:
        response = requests.get(
            WIKIPEDIA_API,
            params=params,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [{"error": "Wikipedia search failed", "details": str(exc)}]

    results = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        page_id = item.get("pageid")
        snippet = clean_html(item.get("snippet", ""))

        article_url = (
            BASE_URL + "/?curid=" + str(page_id)
            if page_id is not None
            else None
        )
        results.append({
            "title": title,
            "snippet": snippet,
            "url": article_url,
        })

    return results

# Keep the evidence database in this project directory.
DATABASE_PATH = Path(__file__).with_name("evidence.db")

# Create the FastAPI application.
app = FastAPI(title="Local Social Media Fact Checker")

# Allowed verdict labels for manually reviewed evidence.
ALLOWED_VERDICTS = {
    "false", "mostly_false", "mixed",
    "mostly_true", "true", "unrated"
}


# ------------------------------------------------------------
# Request formats: the JSON fields accepted by each endpoint.
# ------------------------------------------------------------

class CheckRequest(BaseModel):
    # Text copied from a social-media post.
    text: str = Field(min_length=5, max_length=10000)

    # Language label, reserved for future improvements.
    language: str = "en"


class EvidenceRequest(BaseModel):
    # Claim that a human reviewer has checked.
    claim: str = Field(min_length=5, max_length=2000)

    # Assessment entered by the reviewer.
    verdict: str

    # Explanation for the assessment.
    explanation: str = Field(min_length=3, max_length=3000)

    # Title of the report or document.
    source_title: str = Field(min_length=2, max_length=500)

    # Optional reference URL; the API does not fetch it.
    source_url: str | None = None

    # Relevant passage or notes from the source.
    evidence_text: str = Field(min_length=5, max_length=10000)


# ------------------------------------------------------------
# Database helpers.
# ------------------------------------------------------------

def get_connection():
    # Open the local database.
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database():
    # Create the evidence table if it is missing.
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                explanation TEXT NOT NULL,
                source_title TEXT NOT NULL,
                source_url TEXT,
                evidence_text TEXT NOT NULL
            )
        """)


initialise_database()


# ------------------------------------------------------------
# Basic candidate-claim extraction.
# This is a placeholder, not an AI-based claim extractor.
# ------------------------------------------------------------

def extract_claims(text: str) -> list[str]:
    # Split the post into sentences and lines.
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    claims = []

    for sentence in sentences:
        sentence = sentence.strip()

        # Ignore short fragments and questions.
        if len(sentence) < 15 or sentence.endswith("?"):
            continue

        # Skip a few obvious opinion-style openings.
        lowered = sentence.lower()
        if lowered.startswith((
            "i think ", "i feel ", "i believe ",
            "in my opinion "
        )):
            continue

        claims.append(sentence)

    # Limit the number of candidate claims.
    return claims[:8]


# ------------------------------------------------------------
# Keyword-based local evidence search.
# Keyword overlap is not proof that two claims are equivalent.
# ------------------------------------------------------------

STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "from",
    "was", "were", "are", "is", "has", "have", "had",
    "but", "not", "you", "your", "they", "their", "its",
    "into", "than", "then", "about", "last", "year"
}


def keywords(text: str) -> set[str]:
    # Convert text to lowercase words and remove common words.
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        word for word in words
        if len(word) > 2 and word not in STOP_WORDS
    }


def search_evidence(claim: str) -> list[dict]:
    # Find records that share keywords with the candidate claim.
    claim_words = keywords(claim)

    if not claim_words:
        return []

    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM evidence"
        ).fetchall()

    matches = []

    for row in rows:
        searchable_text = row["claim"] + " " + row["evidence_text"]
        shared = claim_words & keywords(searchable_text)

        # Require at least two shared keywords.
        if len(shared) < 2:
            continue

        score = len(shared) / len(claim_words)

        if score >= 0.35:
            matches.append({
                "stored_claim": row["claim"],
                "verdict": row["verdict"],
                "explanation": row["explanation"],
                "source_title": row["source_title"],
                "source_url": row["source_url"],
                "evidence_text": row["evidence_text"],
                "relevance_score": round(score, 2)
            })

    matches.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    return matches[:5]


# ------------------------------------------------------------
# API endpoints.
# ------------------------------------------------------------

@app.get("/")
def home():
    # Simple endpoint to confirm that the server is running.
    return {
        "status": "ok",
        "service": "Local Social Media Fact Checker",
        "mode": "local_database"
    }


@app.get("/health")
def health():
    # Confirm that the database can be queried.
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")

        return {"status": "healthy", "database": "available"}

    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Local database is unavailable."
        )


@app.post("/evidence")
def add_evidence(item: EvidenceRequest):
    # Store evidence supplied by a human reviewer.
    # The application does not independently verify it.
    verdict = item.verdict.strip().lower()

    if verdict not in ALLOWED_VERDICTS:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed verdicts: {sorted(ALLOWED_VERDICTS)}"
        )

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO evidence (
                claim, verdict, explanation,
                source_title, source_url, evidence_text
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item.claim.strip(),
            verdict,
            item.explanation.strip(),
            item.source_title.strip(),
            item.source_url,
            item.evidence_text.strip()
        ))

        evidence_id = cursor.lastrowid

    return {
        "status": "saved",
        "evidence_id": evidence_id,
        "message": "Saved locally; source accuracy has not been independently verified."
    }


@app.post("/fact-check")
def fact_check(request: CheckRequest):
    # Extract candidate claims from the submitted text.
    claims = extract_claims(request.text)
    results = []

    for claim in claims:
        # Search local, manually reviewed evidence.
        matches = search_evidence(claim)

        # Search Wikipedia separately. These are source leads,
        # not independently verified evidence or verdicts.
        external_results = search_wikipedia(claim, limit=5)
        external_error = next(
            (item.get("details", "External search failed")
             for item in external_results if "error" in item),
            None,
        )
        external_sources = [
            item for item in external_results
            if "error" not in item
        ]

        if not matches:
            results.append({
                "claim": claim,
                "verdict": "unverified",
                "confidence": None,
                "reasoning": (
                    "No relevant local evidence was found. "
                    "External search results are leads for review, "
                    "not proof of whether the claim is true or false."
                ),
                "sources": [],
                "external_sources": external_sources,
                "external_search_error": external_error,
                "method": "local_database_and_external_search",
            })
            continue

        # Retain local matches close to the best keyword score.
        best_score = matches[0]["relevance_score"]
        strong = [
            match for match in matches
            if match["relevance_score"] >= best_score - 0.10
        ]

        # Conflicting local verdicts require human review.
        verdicts = {match["verdict"] for match in strong}

        if len(verdicts) > 1:
            verdict = "unverified"
            reasoning = (
                "Local records have conflicting verdicts. "
                "Human review is needed to resolve the conflict."
            )
        else:
            verdict = strong[0]["verdict"]
            reasoning = strong[0]["explanation"]

        results.append({
            "claim": claim,
            "verdict": verdict,
            "confidence": None,
            "reasoning": reasoning,
            "sources": [
                {
                    "title": match["source_title"],
                    "url": match["source_url"],
                    "evidence_text": match["evidence_text"],
                    "relevance_score": match["relevance_score"],
                }
                for match in strong
            ],
            "external_sources": external_sources,
            "external_search_error": external_error,
            "method": "local_database_and_external_search",
        })

    return {
        "input_text": request.text,
        "language": request.language,
        "claims_extracted": len(claims),
        "results": results,
        "notice": (
            "Prototype: claims are extracted using simple rules. "
            "Local verdicts depend on manually entered evidence. "
            "External search results are leads for human review, "
            "not independently verified verdicts."
        ),
    }


def fact_check_text(text):
    # Extract candidate claims from the submitted text.
    claims = extract_claims(text) 
    results = []

    for claim in claims:
        # Search local, manually reviewed evidence.
        matches = search_evidence(claim)

        # Search Wikipedia separately. These are source leads,
        # not independently verified evidence or verdicts.
        external_results = search_wikipedia(claim, limit=5)
        external_error = next(
            (item.get("details", "External search failed")
             for item in external_results if "error" in item),
            None,
        )
        external_sources = [
            item for item in external_results
            if "error" not in item
        ]

        if not matches:
            results.append({
                "claim": claim,
                "verdict": "unverified",
                "confidence": None,
                "reasoning": (
                    "No relevant local evidence was found. "
                    "External search results are leads for review, "
                    "not proof of whether the claim is true or false."
                ),
                "sources": [],
                "external_sources": external_sources,
                "external_search_error": external_error,
                "method": "local_database_and_external_search",
            })
            continue

        # Retain local matches close to the best keyword score.
        best_score = matches[0]["relevance_score"]
        strong = [
            match for match in matches
            if match["relevance_score"] >= best_score - 0.10
        ]

        # Conflicting local verdicts require human review.
        verdicts = {match["verdict"] for match in strong}

        if len(verdicts) > 1:
            verdict = "unverified"
            reasoning = (
                "Local records have conflicting verdicts. "
                "Human review is needed to resolve the conflict."
            )
        else:
            verdict = strong[0]["verdict"]
            reasoning = strong[0]["explanation"]

        results.append({
            "claim": claim,
            "verdict": verdict,
            "confidence": None,
            "reasoning": reasoning,
            "sources": [
                {
                    "title": match["source_title"],
                    "url": match["source_url"],
                    "evidence_text": match["evidence_text"],
                    "relevance_score": match["relevance_score"],
                }
                for match in strong
            ],
            "external_sources": external_sources,
            "external_search_error": external_error,
            "method": "local_database_and_external_search",
        })

    return {
        "input_text": text,
        "language": request.language,
        "claims_extracted": len(claims),
        "results": results,
        "notice": (
            "Prototype: claims are extracted using simple rules. "
            "Local verdicts depend on manually entered evidence. "
            "External search results are leads for human review, "
            "not independently verified verdicts."
        ),
    }
