"""Connect the team's post photo fetcher to the local image detector."""

from collections.abc import Callable

from image_ai_detector import ImageAIDetector


def score_post_image(
    post_url: str,
    detector: ImageAIDetector,
    fetch_photo: Callable[[str], bytes] | None = None,
) -> float:
    """Fetch one post photo, score its bytes, and return a float from 0 to 1.

    Pass a long-lived detector instance so the model is loaded only once.
    The default fetcher is provided by tweet_extract.py in this repository.
    """
    if fetch_photo is None:
        from tweet_extract import get_photo

        fetch_photo = get_photo

    image_bytes = fetch_photo(post_url)
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Photo fetcher must return nonempty encoded image bytes")
    return detector.score(image_bytes)
