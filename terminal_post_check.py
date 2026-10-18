#!/usr/bin/env python3
"""Prompt for an X/Twitter post and ask the VM to score its attached photo."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_URL = "http://127.0.0.1:8082/detect"


def score_post_from_terminal() -> float:
    post_url = input("Paste an X/Twitter post URL: ").strip()
    if not post_url:
        raise ValueError("Please enter a post URL")

    api_url = os.environ.get("IMAGE_DETECTOR_URL", DEFAULT_API_URL)
    request = Request(
        api_url,
        data=post_url.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            score = json.load(response)
    except HTTPError as error:
        try:
            message = json.load(error).get("error", error.reason)
        except (ValueError, AttributeError):
            message = error.reason
        raise RuntimeError(f"Server returned HTTP {error.code}: {message}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the image detector: {error.reason}") from error

    if not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
        raise RuntimeError(f"Unexpected score from server: {score!r}")
    print(f"AI-generated image score: {score:.6f}")
    return float(score)


if __name__ == "__main__":
    try:
        score_post_from_terminal()
    except (ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
