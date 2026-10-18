# AI-generated image detector

`image_ai_detector.py` accepts an image that Pillow can decode and returns one JSON float from 0 to 1. It corrects EXIF orientation and converts the image to RGB before applying the model's own preprocessing. Scores near 1 indicate stronger AI-generation signal. The score is **not calibrated proof** of origin. Ordinary Photoshop edits are a separate task.

The model is [SteganographIA's ViT image detector](https://huggingface.co/delpot/steganograph-ia-detector), which is distributed under the MIT license. Its model card describes the training images, label order, and limitations. This repository's wrapper code was written for the datathon; the pretrained weights and third-party libraries are attributed here.

The initial [CommunityForensics DeepfakeDet ViT-Small](https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT) model missed one of two fresh AI-generated test images. The current model caught both, and classified six known real photos as real, in a small eight-image check. That check is useful for smoke testing but does not establish general accuracy. The current model's published test results are author-reported, and it can still miss AI images from unfamiliar generators.

## CLI

```bash
python3 image_ai_detector.py photo.jpg
```

## Local API

```bash
python3 image_ai_detector.py --serve
curl -sS -X POST --data-binary @photo.jpg http://127.0.0.1:8082/detect
```

`POST /detect` accepts raw image bytes or an HTTPS X/Twitter post URL sent as `text/plain` or JSON `{"url":"https://x.com/user/status/123"}`. For a URL, it calls the team's `tweet_extract.get_photo()`, feeds the downloaded photo bytes into the model, and returns the same JSON number, for example `0.7312`. The URL path requires `tweet_extract.py` from the teammate's branch on the same machine. `GET /health` confirms the model is loaded. The server binds to localhost by default. Files over 20 MB, images over 50 million pixels, and unsupported or corrupt formats are rejected.

```bash
curl -H 'Content-Type: text/plain' --data-binary \
  'https://x.com/icreatelife/status/2098789935071322416?s=20' \
  http://127.0.0.1:8082/detect
```

On the LinuxONE VM, the Python environment is `/home/linux1/image-detector-env`. Run with its Python executable. The model weights are cached on the VM and are not committed to Git.

For public access, teammate integration, and a full LinuxONE setup guide, see [PUBLIC_IMAGE_API.md](PUBLIC_IMAGE_API.md).

## Call the team's photo fetcher from Python

After `tweet_extract.py` is merged onto the same machine, the integration function calls its `get_photo(post_url)`, passes the returned image bytes to the detector, and returns the float score to its caller:

```python
from image_ai_detector import ImageAIDetector
from post_image_analysis import score_post_image

detector = ImageAIDetector()  # create once when the application starts
score = score_post_image("https://x.com/example/status/123", detector)
```

`tweet_extract.get_photo()` currently returns only the last photo if a post has multiple photos, and raises an error for a post with none. The extraction teammate should define how to handle those cases. This integration function does not copy or merge their code.

To run the hard-coded live smoke test on the VM, place `tweet_extract.py` from the teammate's branch next to these files and run:

```bash
/home/linux1/image-detector-env/bin/python test_live_tweet_image.py
```

The test fetches one known post photo over the network, scores it locally, and prints the score. It requires network access and does not assert that the image is real or AI-generated.

For a screen recording, show the hard-coded URL near the top of `test_live_tweet_image.py`, then run the command above. The output shows the model name, downloaded byte count, score, and a PASS line. Explain that the score is a model signal, not verified ground truth. The displayed score can change if the source image or model weights change.
