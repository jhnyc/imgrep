"""
Image service - handles image scanning, hashing, thumbnail generation, and metadata extraction.
"""
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from PIL import Image as PILImage
import json

from ..core.config import THUMBNAIL_SIZE, IMAGE_EXTENSIONS, THUMBNAILS_DIR


def scan_directory(directory_path: Path) -> List[Path]:
    """Recursively scan directory for image files"""
    if not directory_path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    image_paths = []
    for ext in IMAGE_EXTENSIONS:
        image_paths.extend(directory_path.rglob(f"*{ext}"))
        image_paths.extend(directory_path.rglob(f"*{ext.upper()}"))

    return sorted(set(image_paths))


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file"""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_corpus_hash(image_ids: List[int]) -> str:
    """Compute hash of image corpus for change detection"""
    hasher = hashlib.sha256()
    for img_id in sorted(image_ids):
        hasher.update(str(img_id).encode())
    return hasher.hexdigest()


def generate_thumbnail(
    file_path: Path,
    output_dir: Path = THUMBNAILS_DIR,
    size: tuple[int, int] = None
) -> str:
    """Generate thumbnail and return relative path"""
    if size is None:
        size = (THUMBNAIL_SIZE, THUMBNAIL_SIZE)

    output_dir.mkdir(parents=True, exist_ok=True)

    file_hash = compute_file_hash(file_path)
    thumb_filename = f"{file_hash}.jpg"
    thumb_path = output_dir / thumb_filename

    # Generate if doesn't exist
    if not thumb_path.exists():
        with PILImage.open(file_path) as img:
            # Convert RGBA to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                background = PILImage.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize maintaining aspect ratio
            img.thumbnail(size, PILImage.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85, optimize=True)

    return f"thumbnails/{thumb_filename}"


def get_image_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract image metadata"""
    stat = file_path.stat()
    metadata = {
        "file_size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }

    try:
        with PILImage.open(file_path) as img:
            metadata["width"] = img.width
            metadata["height"] = img.height
            metadata["format"] = img.format
            metadata["mode"] = img.mode
    except Exception as e:
        metadata["error"] = str(e)

    return metadata


def get_thumbnail_url(thumbnail_path: str) -> str:
    """Get URL for thumbnail"""
    return f"/api/thumbnails/{thumbnail_path}" if thumbnail_path else ""


def is_image_path(file_path: Path) -> bool:
    """Check if a file path is an image based on extension"""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS
