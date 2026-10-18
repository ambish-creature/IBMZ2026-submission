#!/usr/bin/env python3
"""Fetch a known X post photo and score it with the local image model."""

from image_ai_detector import MODEL_ID, ImageAIDetector
from post_image_analysis import score_post_image
from tweet_extract import get_photo


POST_URL = "https://x.com/JoeBiden/status/2096966644870394260?s=20"


def main() -> None:
    print(f"Post URL: {POST_URL}", flush=True)
    print(f"[1/3] Loading local model: {MODEL_ID}", flush=True)
    detector = ImageAIDetector()

    def fetch_and_report(post_url: str) -> bytes:
        print("[2/3] Fetching the post photo over the network...", flush=True)
        image_bytes = get_photo(post_url)
        print(f"      Downloaded {len(image_bytes):,} image bytes", flush=True)
        print("[3/3] Sending downloaded bytes directly to the local model...", flush=True)
        return image_bytes

    score = score_post_image(POST_URL, detector, fetch_and_report)
    if not 0.0 <= score <= 1.0:
        raise RuntimeError(f"Model returned a score outside 0–1: {score}")
    print(f"AI-generated image score: {score:.6f}")
    print("PASS: photo fetch and model inference succeeded")


if __name__ == "__main__":
    main()
