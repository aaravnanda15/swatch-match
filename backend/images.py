"""Image checks and clean-up, shared by ingestion and uploads."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import CONFIG

MAX_SIDE = CONFIG["uploads"]["max_side_px"]
MAX_BYTES = CONFIG["uploads"]["max_mb"] * 1024 * 1024

# Refuse absurdly large images (protects against "decompression bomb" files).
Image.MAX_IMAGE_PIXELS = 60_000_000


class BadImage(Exception):
    """Raised with a friendly message when a file is not a usable photo."""


def load_image(data: bytes) -> Image.Image:
    """Turn raw file bytes into a clean RGB photo, or raise BadImage."""
    if not data:
        raise BadImage("The file is empty.")
    if len(data) > MAX_BYTES:
        raise BadImage(f"The photo is too big. Please send one under {CONFIG['uploads']['max_mb']} MB.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise BadImage("That file is not a photo we can read. Please send a JPG, PNG or WEBP.")

    img = ImageOps.exif_transpose(img)  # phone photos are often stored sideways
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # shrinks only, keeps the shape
    return img


def load_image_file(path) -> Image.Image:
    with open(path, "rb") as f:
        return load_image(f.read())


def to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
