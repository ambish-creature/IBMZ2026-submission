# IBMZ2026: social post checker

Paste a public X/Twitter post URL into the desktop app. It fetches the post text
and first attached photo, scores whether the text and image appear AI generated,
and checks the first extracted claim against local reviewer evidence. Wikipedia
results are shown as research leads. You can also run the checker in a terminal.

This README covers installation, model download, startup, and use.

The application has two AI components: `classifier.joblib` scores post text, and the
Hugging Face image model `delpot/steganograph-ia-detector` scores the first attached
photo. The text classifier is included in this repository. The image weights are
downloaded from Hugging Face during setup. The fact checker searches a local SQLite
evidence database and Wikipedia; it needs no AI model or API key.

You need internet access to install packages, download the image model, fetch public
X/Twitter posts through FxTwitter, and search Wikipedia. Use Python **3.12**. There
are two supported layouts below: everything on one computer, or image inference on
an IBM LinuxONE VM with the desktop app on your computer.

## Option A: everything on one computer

### 1. Install Python and download the code

**Ubuntu 24.04 x86_64:**

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip python3-tk
python3 --version
git clone https://github.com/ambish-creature/IBMZ2026-submission.git
cd IBMZ2026-submission
python3 -m venv .venv
source .venv/bin/activate
```

The version check should show Python 3.12.x. Other Linux distributions can use their
Python 3.12 and Tk packages, but the commands above are for Ubuntu 24.04 x86_64.

**macOS Apple Silicon:** Install the Python 3.12 macOS installer from
<https://www.python.org/downloads/> (it includes Tk), then:

```bash
git clone https://github.com/ambish-creature/IBMZ2026-submission.git
cd IBMZ2026-submission
python3.12 -m venv .venv
source .venv/bin/activate
python --version
python -c 'import tkinter; print("Tk ready")'
```

If `import tkinter` fails, use a Python 3.12 installation with Tk. The Homebrew
Python build may require a separate `python-tk` package.

### 2. Install both components

With `.venv` active, on **Ubuntu**:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python -m pip install -r requirements-image-detector.txt
```

On **macOS Apple Silicon**, the image requirement file's `+cpu` PyTorch wheel is
Linux specific, so use this image install command instead:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python -m pip install torch==2.10.0 transformers==5.4.0 Pillow==10.2.0
```

`requirements.txt` is the full project package inventory, including training and
notebook tools. The commands above install only what the working application needs.

### 3. Download and check the AI models

The first command downloads the image model weights and processor into the Hugging
Face cache for the current user. It can take several minutes. The second checks the
bundled text classifier and confirms that class `0` is the AI-written class.

```bash
python -c 'from image_ai_detector import ImageAIDetector; ImageAIDetector(); print("Image model ready")'
python -c 'from backend import score_ai_text; print("Text model ready:", score_ai_text("This is a sample social media post."))'
```

The model cache belongs to the user who ran the command. If you run the service as
another user later, that user must download the weights too.

### 4. Start the image service and use the checker

In terminal 1, from the repository with `.venv` active:

```bash
python image_ai_detector.py --serve
```

Leave it running. In terminal 2:

```bash
cd /path/to/IBMZ2026-submission
source .venv/bin/activate
curl http://127.0.0.1:8082/health
python backend.py 'https://x.com/icreatelife/status/2098789935071322416?s=20'
python ui_desktop.py
```

Replace `/path/to/IBMZ2026-submission` with the clone's actual path. The health response should contain
`"model":"delpot/steganograph-ia-detector"`. The backend command should print
`ai_text_score`, `ai_image_score`, and an empty `errors` object. Paste any public
X/Twitter post URL into the desktop window. A post without a photo correctly has
`ai_image_score: null`.

## Option B: image model on a fresh LinuxONE VM

This layout runs the image model on an Ubuntu 24.04 `s390x` VM and runs the desktop,
text classifier, and fact checker on your laptop. It avoids installing the full
scientific Python stack on `s390x`. You need SSH access to a LinuxONE VM and its
current IP address. Follow your cloud account's SSH key setup; do not share your
private key.

On the **VM**, after signing in:

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip python3-numpy python3-pil
git clone https://github.com/ambish-creature/IBMZ2026-submission.git
cd IBMZ2026-submission
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-image-detector.txt
python -c 'from image_ai_detector import ImageAIDetector; ImageAIDetector(); print("Image model ready")'
python image_ai_detector.py --serve
```

Leave the service running on the VM. It listens on the VM's loopback address, not
on a public port. On your **laptop**, set up Python, clone the repository, create
`.venv`, and install `requirements-desktop.txt` using step 1 and the first two
commands in step 2. Then open an SSH tunnel in another terminal:

```bash
ssh -N -L 8082:127.0.0.1:8082 linux1@YOUR_VM_IP
```

Replace `YOUR_VM_IP` with the VM's current address and `linux1` if your VM has a
different login name. Leave this terminal open. On the laptop, the tunnel makes
the VM image service available at `http://127.0.0.1:8082`. In the laptop's project
`.venv`, run:

```bash
curl http://127.0.0.1:8082/health
python backend.py 'https://x.com/icreatelife/status/2098789935071322416?s=20'
python ui_desktop.py
```

If you intentionally use a separately hosted image service instead of the local
service or SSH tunnel, set `IMAGE_DETECTOR_URL` to its full `/detect` URL before
starting `backend.py` or `ui_desktop.py`. See [PUBLIC_IMAGE_API.md](PUBLIC_IMAGE_API.md)
for the optional Nginx public endpoint setup.

## Use the image API directly

With the image service running, send image bytes or an HTTPS X/Twitter post URL:

```bash
curl --data-binary @photo.jpg http://127.0.0.1:8082/detect
curl -H 'Content-Type: text/plain' --data-binary \
  'https://x.com/icreatelife/status/2098789935071322416?s=20' \
  http://127.0.0.1:8082/detect
```

`GET /health` confirms the model is loaded. `POST /detect` returns one JSON number
between 0 and 1. See [IMAGE_DETECTOR.md](IMAGE_DETECTOR.md) for accepted image
formats and the model interface. The public VM API is optional; its old IP address
may change.

## What the results mean

- `ai_text_score` and `ai_image_score` are model signals from 0 to 1, not proof or
  calibrated probabilities.
- The fact checker returns `unverifiable` when the local evidence database has no
  matching reviewer-entered evidence. Wikipedia results are research leads only.
- The system does not currently detect Photoshop edits or verify every claim in a
  post. The desktop shows the first extracted claim and the first attached photo.
- The saved text classifier was trained on limited data and may not generalize to
  short posts.

`requirements-desktop.txt` and `requirements-image-detector.txt` install the
working application. `requirements.txt` inventories the full project, including
training and notebook tools. LinuxONE `s390x` may need system-provided scientific
Python packages instead of PyPI wheels.

The external package, model, data, and service links are listed in
[THIRD_PARTY_RESOURCES.txt](THIRD_PARTY_RESOURCES.txt).
