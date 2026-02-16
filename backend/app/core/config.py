"""Application constants and configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
UPLOADS_DIR = DATA_DIR / "uploads"
MODELS_DIR = DATA_DIR / "models"

# Embedding Configuration (local SigLIP model)
SIGLIP_MODEL_NAME = os.getenv("SIGLIP_MODEL_NAME", "google/siglip-base-patch16-512")
SIGLIP_DEVICE = os.getenv("SIGLIP_DEVICE", "auto")  # Options: "auto", "cuda", "cpu", "mps"

# Database Configuration
DB_NAME = os.getenv("DB_NAME", "app.db")
DB_PATH = DB_DIR / DB_NAME
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Server Configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8001"))
RELOAD = os.getenv("RELOAD", "true").lower() == "true"

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(",")

# Image Processing
THUMBNAIL_SIZE = int(os.getenv("THUMBNAIL_SIZE", "256"))
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

# Embedding Configuration
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "12"))
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "60.0"))

# Clustering Configuration
CANVAS_SIZE = float(os.getenv("CANVAS_SIZE", "2000"))
UMAP_N_NEIGHBORS = int(os.getenv("UMAP_N_NEIGHBORS", "15"))
UMAP_MIN_DIST = float(os.getenv("UMAP_MIN_DIST", "0.1"))

# Security
# Comma-separated list of allowed directory prefixes for scanning
ALLOWED_DIRECTORY_PREFIXES = os.getenv("ALLOWED_DIRECTORY_PREFIXES", "").split(",") if os.getenv("ALLOWED_DIRECTORY_PREFIXES") else []

# Ensure directories exist
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Chroma configuration
CHROMA_DATA_PATH = DATA_DIR / "chroma"
CHROMA_COLLECTION_NAME = "images"
