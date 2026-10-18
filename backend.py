"""Connect post extraction, source review, and the two AI detectors."""

import json
import os
from functools import lru_cache
from pathlib import Path

import requests

from tweet_extract import download_images, get_post

ROOT = Path(__file__).resolve().parent
IMAGE_DETECTOR_URL = os.getenv("IMAGE_DETECTOR_URL", "http://127.0.0.1:8082/detect")


def fetch_tweet(url: str) -> dict:
    return get_post(url)


def check_claim(text: str) -> dict:
    from fact_checker.app import CheckRequest, fact_check

    if len(text.strip()) < 5:
        return {"claim": text, "verdict": "unverifiable", "confidence": None,
                "summary": "This post has too little text to check.", "sources": [],
                "external_sources": [], "method": "No factual claim extracted."}
    checked = fact_check(CheckRequest(text=text[:10000]))
    claims = checked["results"]
    if not claims:
        return {"claim": text[:200], "verdict": "unverifiable", "confidence": None,
                "summary": "No checkable factual claim was extracted.", "sources": [],
                "external_sources": [], "method": "Rule based claim extraction."}
    first = claims[0]
    verdict = first["verdict"]
    if verdict in ("unverified", "unrated", "mostly_false"):
        verdict = "unverifiable" if verdict != "mostly_false" else "misleading"
    return {
        "claim": first["claim"], "verdict": verdict, "confidence": first["confidence"],
        "summary": first["reasoning"], "sources": first["sources"],
        "external_sources": first["external_sources"],
        "method": "Claims are split by simple rules and compared with local reviewer records. Wikipedia links are research leads, not proof.",
        "claims_extracted": checked["claims_extracted"],
        "external_search_error": first.get("external_search_error"),
    }


@lru_cache(maxsize=1)
def _text_model():
    import joblib
    return joblib.load(ROOT / "classifier.joblib")


def score_ai_text(text: str) -> float:
    model = _text_model()
    classes = list(model.classes_)
    if 0 not in classes:
        raise ValueError("Saved text classifier lacks the AI-written class (0).")
    return float(model.predict_proba([text])[0][classes.index(0)])


def score_ai_image(photo_bytes: bytes) -> float:
    response = requests.post(
        IMAGE_DETECTOR_URL, data=photo_bytes,
        headers={"Content-Type": "application/octet-stream"}, timeout=90,
    )
    response.raise_for_status()
    value = float(response.json())
    if not 0 <= value <= 1:
        raise ValueError("The image detector returned a score outside 0–1.")
    return value


def analyze_post(url: str) -> dict:
    post = fetch_tweet(url)
    text = post["text"]
    if not text and not post["photo_urls"]:
        raise ValueError("The post has no text or photo to analyse.")
    result = {"post": post, "fact_check": None, "ai_text_score": None,
              "ai_image_score": None, "errors": {}}
    if text:
        try:
            result["fact_check"] = check_claim(text)
        except Exception as exc:
            result["errors"]["fact_check"] = str(exc)
        try:
            result["ai_text_score"] = score_ai_text(text)
        except Exception as exc:
            result["errors"]["ai_text"] = str(exc)
    if post["photo_urls"]:
        try:
            result["ai_image_score"] = score_ai_image(download_images(post["photo_urls"]))
        except Exception as exc:
            result["errors"]["ai_image"] = str(exc)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("Usage: python backend.py 'https://x.com/user/status/123'")
    print(json.dumps(analyze_post(sys.argv[1]), indent=2, ensure_ascii=False))
