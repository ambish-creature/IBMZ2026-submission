# IBMZ2026

## Run the integrated post checker

Use Python 3.12 in an environment with Tk support for the desktop window. Install the packages from `requirements.txt`, then run:

```bash
python ui_desktop.py
```

Paste a public `https://x.com/<user>/status/<id>` link. The backend fetches its text and first photo via FxTwitter, checks candidate claims against locally entered evidence and Wikipedia research leads, scores the text with the saved `classifier.joblib`, and sends photo bytes to the image model on the LinuxONE VM. The desktop shows all available results and any unavailable component. You can run the same analysis without a desktop window:

```bash
python backend.py 'https://x.com/icreatelife/status/2098789935071322416?s=20'
```

`IMAGE_DETECTOR_URL` overrides the image service URL. Set it to `http://127.0.0.1:8082/detect` when running on the VM. The default is the team's public image endpoint. The saved text classifier needs scikit-learn 1.9.0. On macOS, use a Python distribution that includes Tk; Homebrew's Python may require a separate `python-tk` package.

Fact verdicts come only from local reviewer entered evidence. An empty evidence database returns **unverifiable**, even when Wikipedia returns links. The two AI scores are model signals from 0 to 1, not calibrated probabilities or proof that content was AI generated. The text classifier was trained on a limited dataset and may not generalize to short posts.

## AI-Generated Image Detection API

The image detector runs on the LinuxONE VM. Its public endpoint is `POST http://148.100.109.177/image/detect`; programs on the VM can use `http://127.0.0.1:8082/detect`.

Send either raw image bytes or an HTTPS X/Twitter post URL. The URL path fetches the post's attached photo and feeds its bytes to the model. The response is one JSON number from `0.0` to `1.0`; higher values indicate a stronger AI-generation signal, not proof of origin.

```bash
curl --data-binary @photo.jpg http://148.100.109.177/image/detect
curl -H 'Content-Type: text/plain' --data-binary \
  'https://x.com/icreatelife/status/2098789935071322416?s=20' \
  http://148.100.109.177/image/detect
```

See [IMAGE_DETECTOR.md](IMAGE_DETECTOR.md) for the model interface and [PUBLIC_IMAGE_API.md](PUBLIC_IMAGE_API.md) for VM setup and integration instructions.

## Python dependencies

The direct links for packages, pretrained models, datasets, APIs, tools, and demo resources are listed in [THIRD_PARTY_RESOURCES.txt](THIRD_PARTY_RESOURCES.txt).

Use Python 3.12 and install the project packages with `python3 -m pip install -r requirements.txt`. On Linux, the desktop UI also needs the system Tk package (for Ubuntu: `sudo apt-get install python3-tk`). The requirement file uses the official PyTorch CPU wheel index for the LinuxONE image detector. The saved `classifier.joblib` was made with scikit-learn 1.9.0, so that version is pinned.

LinuxONE `s390x` has fewer prebuilt Python wheels. On our VM, a pip dry run could not find a binary `pandas` wheel; use a compatible preinstalled package or build it from source if needed. This file lists every project's pip dependency, but the VM may need additional system packages to install them.
