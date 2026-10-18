# Let other people use the image detector

The model runs on the LinuxONE VM, not on a visitor's computer. Nginx accepts public requests on port 80 and forwards only the image API routes to the Python process on `127.0.0.1:8082`.

## Working address on this VM

For a terminal or another backend, send **raw image bytes**:

```bash
curl --fail-with-body --data-binary @photo.jpg \
  http://148.100.109.177/image/detect
```

The response is a JSON number such as `0.7312`. It is an AI-image **model score**, not proof or a calibrated probability. A score near 1 is a stronger AI-generation signal.

You can also send a post URL. The server fetches the post's attached photo and passes its bytes to the same model:

```bash
curl --fail-with-body -H 'Content-Type: text/plain' --data-binary \
  'https://x.com/icreatelife/status/2098789935071322416?s=20' \
  http://148.100.109.177/image/detect
```

JSON `{"url":"https://x.com/user/status/123"}` with `Content-Type: application/json` also works. URL input supports only HTTPS X/Twitter post links and requires `tweet_extract.py` on the VM. A post without an attached photo returns HTTP 400. The link preview card is not used.

To paste a URL interactively **on the VM**, run the standard-library client (the model is already running in its service):

```bash
cd /home/linux1
python3 terminal_post_check.py
```

It prompts for the post URL and prints the score or an error. To run the same client from a different computer, set `IMAGE_DETECTOR_URL=http://148.100.109.177/image/detect` before `python3 terminal_post_check.py`.

Check that the service is up with:

```bash
curl http://148.100.109.177/image/health
```

For byte input, the endpoint accepts Pillow-decodable images such as JPEG, PNG, and WebP, up to 20 MB and 50 million pixels. It returns HTTP 400 with an error JSON object for an invalid image or post URL. Nginx returns HTTP 413 for a body over its size limit and HTTP 429 if the per-IP request rate is exceeded. A remote browser can POST to this endpoint because Nginx answers CORS preflight requests. An HTTPS website cannot call this HTTP endpoint from a browser because browsers block mixed content; see **HTTPS** below.

The endpoint is currently public and unauthenticated. Only use public or test photos over this HTTP address: HTTP does not encrypt uploads. The VM IP can change if the cloud instance is replaced.

## What the teammate building the UI should do

The UI should send the selected `File` directly as the request body. Do **not** use `FormData` or multipart uploads for this endpoint.

```javascript
async function scoreImage(file) {
  const response = await fetch("http://148.100.109.177/image/detect", {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!response.ok) throw new Error(`Image analysis failed: ${response.status}`);
  return await response.json(); // number from 0 to 1
}

async function scorePost(postUrl) {
  const response = await fetch("http://148.100.109.177/image/detect", {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: postUrl,
  });
  if (!response.ok) throw new Error(`Post analysis failed: ${response.status}`);
  return await response.json(); // same 0-to-1 image score
}
```

If the team backend calls this from **inside the same VM**, use `http://127.0.0.1:8082/detect` instead. It has the same request and response format and avoids a public network trip. An ordinary visitor needs only the team's website; they do not need SSH, Python, or a copy of the model.

## Recreate the server on a fresh Ubuntu 24.04 LinuxONE VM

These steps assume an `s390x` VM, a sudo-capable user named `linux1`, and Python 3.12. They install our wrapper and a third-party pretrained model; no model weights are stored in Git. Run commands on the VM unless the step says otherwise.

1. Connect and clone the complete public submission. Replace the IP if it changes:

   ```bash
   ssh linux1@148.100.109.177
   git clone https://github.com/ambish-creature/IBMZ2026-submission.git
   cd IBMZ2026-submission
   ```

2. Install system packages and the Python environment. On this architecture, use the official PyTorch CPU wheel index:

   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-venv python3-pip python3-numpy python3-pil nginx
   python3 -m venv --system-site-packages /home/linux1/image-detector-env
   /home/linux1/image-detector-env/bin/python -m pip install --upgrade pip
   /home/linux1/image-detector-env/bin/python -m pip install \
     -r requirements-image-detector.txt
   ```

3. Copy the image service and photo fetcher to the location expected by the service, then load the model once. The first load downloads the model from Hugging Face and can take a while:

   ```bash
   cp image_ai_detector.py post_image_analysis.py tweet_extract.py /home/linux1/
   /home/linux1/image-detector-env/bin/python -c \
     'from image_ai_detector import ImageAIDetector; ImageAIDetector(); print("model ready")'
   ```

4. Install and start the private model service:

   ```bash
   sudo install -m 644 deploy/image-detector.service \
     /etc/systemd/system/ibmz-image-detector.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now ibmz-image-detector.service
   curl http://127.0.0.1:8082/health
   ```

5. Install the public Nginx gateway. Edit `server_name` in `deploy/image-detector.nginx.conf` if your VM has a different IP or a domain:

   ```bash
   sudo install -m 644 deploy/image-detector.nginx.conf \
     /etc/nginx/conf.d/image-detector.conf
   sudo nginx -t
   sudo systemctl enable --now nginx
   sudo systemctl reload nginx
   curl -H 'Host: 148.100.109.177' http://127.0.0.1/image/health
   ```

6. This VM's firewall allows SSH but rejects other inbound traffic by default. Install the supplied boot service, which opens TCP port 80 before the reject rule:

   ```bash
   sudo install -m 755 deploy/open-image-http-port.sh \
     /usr/local/sbin/open-image-http-port
   sudo install -m 644 deploy/image-detector-firewall.service \
     /etc/systemd/system/image-detector-firewall.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now image-detector-firewall.service
   ```

   If a cloud security group also filters traffic, allow inbound TCP 80 there. From a **different machine**, run `curl http://YOUR_VM_IP/image/health`, then POST a real test image. A request tested only from inside the VM does not prove that visitors can reach it.

## HTTPS for a deployed website

Use a DNS name pointing to the VM. Change Nginx `server_name` to that name, open inbound TCP 443 in the VM and any cloud firewall, then install a certificate. Ubuntu's packages provide an Nginx integration:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
sudo certbot renew --dry-run
```

Update the frontend URL to `https://YOUR_DOMAIN/image/detect`. Avoid asking visitors to upload private photos until HTTPS is working. For a longer-lived public service, add authentication and stronger abuse controls before inviting unrestricted traffic.

## Useful checks

```bash
sudo systemctl status ibmz-image-detector nginx image-detector-firewall --no-pager
sudo journalctl -u ibmz-image-detector -n 50 --no-pager
sudo nginx -t
curl http://127.0.0.1:8082/health
curl http://YOUR_VM_IP/image/health
```

The source code is original project code in `image_ai_detector.py`. The pretrained model is [delpot/steganograph-ia-detector](https://huggingface.co/delpot/steganograph-ia-detector), and the Python dependencies are third-party libraries.
