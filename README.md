# IBMZ2026

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
