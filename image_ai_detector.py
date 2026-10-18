#!/usr/bin/env python3
"""Return an AI-generation score for a decoded image, using a local vision model."""

import argparse
import io
import json
import math
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError
import requests
import torch
from transformers import ViTForImageClassification, ViTImageProcessorPil


MODEL_ID = "delpot/steganograph-ia-detector"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_POST_URL_BYTES = 2048
Image.MAX_IMAGE_PIXELS = 50_000_000


class ImageAIDetector:
    def __init__(self):
        torch.set_num_threads(3)
        self.processor = ViTImageProcessorPil.from_pretrained(MODEL_ID)
        self.model = ViTForImageClassification.from_pretrained(MODEL_ID)
        self.model.eval()
        labels = {str(label).lower(): int(index) for index, label in self.model.config.id2label.items()}
        if self.model.config.num_labels != 2 or "ai_generated" not in labels:
            raise RuntimeError("Expected real and ai_generated output labels")
        self.ai_label_index = labels["ai_generated"]

    def score(self, image_bytes: bytes) -> float:
        if not image_bytes or len(image_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError("Image must be nonempty and at most 20 MB")
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError("Image exceeds 50 million pixels")
                rgb = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("Unsupported or corrupt image") from error

        inputs = self.processor(rgb, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(**inputs).logits
            value = float(torch.softmax(logits, dim=-1)[0, self.ai_label_index].item())
        if not math.isfinite(value):
            raise RuntimeError("Model returned a non-finite score")
        return value


def normalized_post_url(value: str) -> str:
    if not value or len(value.encode("utf-8")) > MAX_POST_URL_BYTES:
        raise ValueError("Post URL must be nonempty and at most 2048 bytes")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or not re.fullmatch(r"/[A-Za-z0-9_]{1,15}/status/[0-9]+/?", parsed.path)
    ):
        raise ValueError("Expected an HTTPS X/Twitter post URL")
    return "https://x.com" + parsed.path.rstrip("/")


def score_request(detector: ImageAIDetector, body: bytes, content_type: str) -> float:
    kind = content_type.split(";", 1)[0].strip().lower()
    if kind == "application/json":
        if len(body) > MAX_POST_URL_BYTES + 32:
            raise ValueError("Post URL request is too large")
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("url"), str):
            raise ValueError('Expected JSON object with a string "url"')
        post_url = data["url"]
    elif kind == "text/plain" or (len(body) <= MAX_POST_URL_BYTES and body.startswith(b"http")):
        post_url = body.decode("utf-8")
    else:
        return detector.score(body)

    from post_image_analysis import score_post_image

    try:
        return score_post_image(normalized_post_url(post_url), detector)
    except UnboundLocalError as error:
        # The current team fetcher raises this when a post has no attached photo.
        raise ValueError("Post has no attached photo") from error


def serve(detector: ImageAIDetector, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            self._respond(200, {"status": "ok", "model": MODEL_ID})

        def do_POST(self):
            if self.path != "/detect":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_UPLOAD_BYTES:
                    raise ValueError("Image must be nonempty and at most 20 MB")
                score = score_request(detector, self.rfile.read(length), self.headers.get("Content-Type", ""))
            except (ValueError, UnicodeError, Image.DecompressionBombError) as error:
                self._respond(400, {"error": str(error)})
                return
            except (requests.RequestException, KeyError, ModuleNotFoundError):
                self._respond(502, {"error": "Post photo could not be fetched"})
                return
            self._respond(200, score)

        def _respond(self, status: int, data):
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    HTTPServer((host, port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path, help="Image to score")
    parser.add_argument("--serve", action="store_true", help="Start a local HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    args = parser.parse_args()
    if args.serve == (args.image is not None):
        parser.error("Provide either an image path or --serve")
    detector = ImageAIDetector()
    if args.serve:
        serve(detector, args.host, args.port)
    else:
        print(json.dumps(detector.score(args.image.read_bytes())))


if __name__ == "__main__":
    main()
