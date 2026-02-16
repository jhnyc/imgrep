"""Application constants and configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
UPLOADS_DIR = DATA_DIR / "uploads"

# API Configuration
JINA_API_KEY = os.getenv("JINA_API_KEY")
if not JINA_API_KEY:
    raise Exception("JINA API key not set. Set JINA_API_KEY environment variable for production.")

JINA_API_URL = os.getenv("JINA_API_URL", "https://api.jina.ai/v1/embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "jina-clip-v2")

# Database Configuration
DB_NAME = os.getenv("DB_NAME", "app.db")
DB_PATH = DB_DIR / DB_NAME
# Use libsql dialect for native vector search support
DATABASE_URL = f"sqlite+libsql:///{DB_PATH}"

# Embedding Configuration  
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))  # jina-clip-v2 outputs 1024 dims

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
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "2"))
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "60.0"))

# Retry Queue Configuration
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "3"))
RETRY_BATCH_SIZE = int(os.getenv("RETRY_BATCH_SIZE", "1"))
RETRY_BASE_DELAY_SECONDS = int(os.getenv("RETRY_BASE_DELAY_SECONDS", "60"))  # Base delay for exponential backoff

# Clustering Configuration
CANVAS_SIZE = float(os.getenv("CANVAS_SIZE", "2000"))
UMAP_N_NEIGHBORS = int(os.getenv("UMAP_N_NEIGHBORS", "15"))
UMAP_MIN_DIST = float(os.getenv("UMAP_MIN_DIST", "0.1"))
PROJECTION_RETRAIN_THRESHOLD = float(os.getenv("PROJECTION_RETRAIN_THRESHOLD", "0.2"))

# Security
# Comma-separated list of allowed directory prefixes for scanning
ALLOWED_DIRECTORY_PREFIXES = os.getenv("ALLOWED_DIRECTORY_PREFIXES", "").split(",") if os.getenv("ALLOWED_DIRECTORY_PREFIXES") else []

# Ensure directories exist
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
