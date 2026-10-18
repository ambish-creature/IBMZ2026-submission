import re
import requests

def get_tweet(url: str):
    m = re.search(r"(?:twitter|x)\.com/([^/]+)/status/(\d+)", url)
    if not m:
        raise ValueError("Not a valid tweet URL")
    user, tweet_id = m.groups()

    r = requests.get(f"https://api.fxtwitter.com/{user}/status/{tweet_id}", timeout=10)
    r.raise_for_status()
    tweet = r.json()["tweet"]

    text = tweet["text"]
    return text

def get_photo(url: str):
    m = re.search(r"(?:twitter|x)\.com/([^/]+)/status/(\d+)", url)
    if not m:
        raise ValueError("Not a valid tweet URL")
    user, tweet_id = m.groups()

    r = requests.get(f"https://api.fxtwitter.com/{user}/status/{tweet_id}", timeout=10)
    r.raise_for_status()
    tweet = r.json()["tweet"]

    photos = [p["url"] for p in tweet.get("media", {}).get("photos", [])]
    photo_byte_data = download_images(photos)
    return photo_byte_data

def download_images(urls, prefix="tweet_img"):
    for i, u in enumerate(urls, 1):
        data = requests.get(u, timeout=10).content
    
    return(data)
        


#ipt = "https://x.com/JoeBiden/status/2096966644870394260?s=20"
#print(get_tweet(ipt))
#print(get_photo(ipt)[0:100])
