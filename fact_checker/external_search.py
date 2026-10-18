import re
from html import unescape

import requests

BASE_URL = "https" + "://" + "en.wikipedia.org"
WIKIPEDIA_API = BASE_URL + "/w/api.php"


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


if __name__ == "__main__":
    test_query = "Earth revolves around the Sun"
    print("Search query:", test_query, "\n")
    for result in search_wikipedia(test_query):
        print(result)
