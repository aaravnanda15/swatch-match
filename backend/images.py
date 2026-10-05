"""Image checks and clean-up, shared by ingestion and uploads."""

import io

import numpy as np

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import CONFIG

MAX_SIDE = CONFIG["uploads"]["max_side_px"]
MAX_BYTES = CONFIG["uploads"]["max_mb"] * 1024 * 1024

# "image/jpeg" -> "JPEG" (Pillow's name)
ALLOWED_FORMATS = {t.split("/")[1].upper().replace("JPG", "JPEG") for t in CONFIG["uploads"]["allowed_types"]}

# decompression-bomb guard
Image.MAX_IMAGE_PIXELS = 60_000_000


class BadImage(Exception):
    """Raised with a friendly message when a file is not a usable photo."""


def load_image(data: bytes) -> Image.Image:
    if not data:
        raise BadImage("The file is empty.")
    if len(data) > MAX_BYTES:
        raise BadImage(f"The photo is too big. Please send one under {CONFIG['uploads']['max_mb']} MB.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise BadImage("That file is not a photo we can read. Please send a JPG, PNG or WEBP.") from e
    # Check the real format, not the file name (a renamed PDF or GIF is caught here).
    if img.format not in ALLOWED_FORMATS:
        raise BadImage(f"{img.format or 'This'} files are not supported. Please send a JPG, PNG or WEBP photo.")

    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def load_image_file(path) -> Image.Image:
    with open(path, "rb") as f:
        return load_image(f.read())


def to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def colour_profile(img: Image.Image):
    """Cheap colour summary of the middle of a photo (edges are often background)."""
    w, h = img.size
    middle = img.crop((int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8))).resize((64, 64))
    pixels = list(middle.convert("HSV").getdata())
    brightness = sum(v for _, _, v in pixels) / len(pixels) / 255
    # Most common hue among clearly coloured pixels, in 12 slices of 30 degrees
    slices = [0] * 12
    for hue, sat, val in pixels:
        if sat > 64 and val > 50:
            slices[hue * 12 // 256] += 1
    hue = None
    if sum(slices) > len(pixels) * 0.2:
        hue = slices.index(max(slices)) * 30 + 15
    return {"brightness": brightness, "hue": hue}


def colour_histogram(img: Image.Image):
    """Hue, saturation and brightness of the middle of a photo, as 192 shares that add up to 1."""
    w, h = img.size
    middle = img.crop((int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.85))).resize((96, 96))
    hsv = np.asarray(middle.convert("HSV")).reshape(-1, 3).astype(int)
    bins = (hsv[:, 0] * 12 // 256) * 16 + (hsv[:, 1] * 4 // 256) * 4 + hsv[:, 2] * 4 // 256
    counts = np.bincount(bins, minlength=192).astype(float)
    return counts / counts.sum()
