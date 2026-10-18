"""Fetch public X/Twitter posts through FxTwitter for the prototype."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

POST_PATH = re.compile(r"/([A-Za-z0-9_]+)/status/(\d+)/?")


def parse_post_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in {
        "x.com", "www.x.com", "mobile.x.com", "twitter.com",
        "www.twitter.com", "mobile.twitter.com",
    }:
        raise ValueError("Use an HTTPS X/Twitter post link.")
    match = POST_PATH.fullmatch(parsed.path)
    if not match:
        raise ValueError("The link must contain /username/status/post_id.")
    return match.groups()


def get_post(url: str) -> dict:
    user, post_id = parse_post_url(url)
    response = requests.get(f"https://api.fxtwitter.com/{user}/status/{post_id}", timeout=15)
    response.raise_for_status()
    tweet = response.json().get("tweet")
    if not isinstance(tweet, dict):
        raise ValueError("This post is unavailable through the public post service.")
    media = tweet.get("media") or {}
    photos = [photo["url"] for photo in media.get("photos", []) if photo.get("url")]
    return {
        "author": "@" + str((tweet.get("author") or {}).get("screen_name") or user),
        "text": str(tweet.get("text") or ""),
        "photo_urls": photos,
        "url": url,
    }


def get_tweet(url: str) -> str:
    return get_post(url)["text"]


def get_photo(url: str) -> bytes | None:
    photos = get_post(url)["photo_urls"]
    return download_images(photos)


def download_images(urls, prefix="tweet_img") -> bytes | None:
    """Compatibility helper: return the first image as bytes, or None."""
    if not urls:
        return None
    response = requests.get(urls[0], timeout=20)
    response.raise_for_status()
    if not response.headers.get("Content-Type", "").lower().startswith("image/"):
        raise ValueError("The post attachment is not an image.")
    if len(response.content) > 15_000_000:
        raise ValueError("The post image is too large to analyse.")
    return response.content
