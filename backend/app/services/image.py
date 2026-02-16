import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from PIL import Image as PILImage
import json

from ..core.config import THUMBNAIL_SIZE, IMAGE_EXTENSIONS, THUMBNAILS_DIR


def scan_directory(directory_path: Path, extensions: Optional[List[str]] = None) -> List[Path]:
    """Recursively scan directory for image files"""
    if not directory_path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    ext_list = extensions if extensions else list(IMAGE_EXTENSIONS)
    # Ensure extensions start with dot and are lower case for robust matching if needed, 
    # but glob is case sensitive on some OS.
    # rglob is recursive.
    
    image_paths = []
    # Use set to avoid duplicates if extensions overlap or casing differs
    seen_paths = set()
    
    for ext in ext_list:
        # Handle case variations if needed, but simple rglob is usually enough
        # We try both lower and upper case to cover most bases
        patterns = [f"*{ext}", f"*{ext.upper()}"]
        if ext.startswith("."):
             patterns = [f"*{ext}", f"*{ext.upper()}"]
        else:
             patterns = [f"*.{ext}", f"*.{ext.upper()}"]

        for pattern in patterns:
            for path in directory_path.rglob(pattern):
                if path.is_file() and str(path) not in seen_paths:
                    image_paths.append(path)
                    seen_paths.add(str(path))

    return sorted(image_paths)


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
    size: Optional[Tuple[int, int]] = None
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


def is_image_path(file_path: Path) -> bool:
    """Check if a file path is an image based on extension"""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS
