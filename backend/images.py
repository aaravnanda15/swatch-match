"""Image checks and clean-up, shared by ingestion and uploads."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import CONFIG

MAX_SIDE = CONFIG["uploads"]["max_side_px"]
MAX_BYTES = CONFIG["uploads"]["max_mb"] * 1024 * 1024

# "image/jpeg" in config.yaml -> "JPEG", the name Pillow uses for the format.
ALLOWED_FORMATS = {t.split("/")[1].upper().replace("JPG", "JPEG") for t in CONFIG["uploads"]["allowed_types"]}

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
    # Check the real format, not the file name (a renamed PDF or GIF is caught here).
    if img.format not in ALLOWED_FORMATS:
        raise BadImage(f"{img.format or 'This'} files are not supported. Please send a JPG, PNG or WEBP photo.")

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
