"""
SigLIP local embedding model using Hugging Face transformers.
Supports google/siglip-base-patch16-512 and similar models.
"""
import io
from functools import lru_cache
from pathlib import Path
from typing import List, Union

import torch
from PIL import Image as PILImage
from transformers import SiglipModel, SiglipProcessor

from ...core.config import SIGLIP_MODEL_NAME, SIGLIP_DEVICE


class SiglipEmbedder:
    """
    Local SigLIP embedder using Hugging Face transformers.
    This runs locally and doesn't require an API key.
    """

    def __init__(
        self,
        model_name: str = SIGLIP_MODEL_NAME,
        device: str = SIGLIP_DEVICE,
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None
        self._embedding_dim = None
        self._actual_device = None  # Store the actual device after resolution

    @property
    def model(self):
        """Lazy load the model"""
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def processor(self):
        """Lazy load the processor"""
        if self._processor is None:
            self._load_model()
        return self._processor

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension"""
        if self._embedding_dim is None:
            # Load model to get dimension
            _ = self.model
        return self._embedding_dim

    def _load_model(self):
        """Load the SigLIP model and processor"""
        # Determine device
        if self.device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        else:
            device = self.device

        self._actual_device = device
        print(f"[SigLIP] Loading model {self.model_name} on {device}...")

        try:
            # Try loading with trust_remote_code for newer models
            self._processor = SiglipProcessor.from_pretrained(
                self.model_name,
                do_resize=True,
                do_center_crop=True,
                do_normalize=True,
            )
            self._model = SiglipModel.from_pretrained(self.model_name).to(device)
            self._model.eval()
        except Exception as e:
            print(f"[SigLIP] Error loading model: {e}")
            print(f"[SigLIP] Retrying with default settings...")
            # Retry with minimal settings
            self._processor = SiglipProcessor.from_pretrained(self.model_name)
            self._model = SiglipModel.from_pretrained(self.model_name).to(device)
            self._model.eval()

        # Get embedding dimension from vision model
        # SigLIP base outputs 768-dim embeddings
        self._embedding_dim = self._model.config.vision_config.hidden_size

        print(f"[SigLIP] Model loaded. Embedding dim: {self._embedding_dim}")

    def embed_image(
        self,
        image: Union[bytes, str, Path, PILImage.Image],
    ) -> List[float]:
        """
        Embed a single image.

        Args:
            image: Can be bytes, file path, Path object, or PIL Image

        Returns:
            Embedding vector as list of floats
        """
        # Convert to PIL Image if needed
        if isinstance(image, bytes):
            pil_image = PILImage.open(io.BytesIO(image)).convert("RGB")
        elif isinstance(image, (str, Path)):
            pil_image = PILImage.open(str(image)).convert("RGB")
        elif isinstance(image, PILImage.Image):
            pil_image = image.convert("RGB")
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")

        with torch.no_grad():
            inputs = self.processor(images=pil_image, return_tensors="pt")
            # Move inputs to the correct device
            inputs = {k: v.to(self._actual_device) if isinstance(v, torch.Tensor) else v
                     for k, v in inputs.items()}
            image_features = self.model.get_image_features(**inputs)
            # Normalize to unit length
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            embedding = image_features.cpu().squeeze(0).tolist()

        return embedding

    def embed_images_batch(
        self,
        images: List[Union[bytes, str, Path, PILImage.Image]],
    ) -> List[List[float]]:
        """
        Embed multiple images in a batch.

        Args:
            images: List of images (bytes, file paths, Path objects, or PIL Images)

        Returns:
            List of embedding vectors
        """
        # Convert all to PIL Images
        pil_images = []
        for img in images:
            if isinstance(img, bytes):
                pil_images.append(PILImage.open(io.BytesIO(img)).convert("RGB"))
            elif isinstance(img, (str, Path)):
                pil_images.append(PILImage.open(str(img)).convert("RGB"))
            elif isinstance(img, PILImage.Image):
                pil_images.append(img.convert("RGB"))
            else:
                raise TypeError(f"Unsupported image type: {type(img)}")

        with torch.no_grad():
            inputs = self.processor(images=pil_images, return_tensors="pt")
            # Move inputs to the correct device
            inputs = {k: v.to(self._actual_device) if isinstance(v, torch.Tensor) else v
                     for k, v in inputs.items()}
            image_features = self.model.get_image_features(**inputs)
            # Normalize to unit length
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            embeddings = image_features.cpu().tolist()

        return embeddings

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text query.
        Note: SigLIP is primarily vision-focused; text embeddings may not work
        as well for cross-modal retrieval compared to CLIP models.

        Args:
            text: The text to embed

        Returns:
            Embedding vector as list of floats
        """
        with torch.no_grad():
            inputs = self.processor(text=text, return_tensors="pt")
            # Move inputs to the correct device
            inputs = {k: v.to(self._actual_device) if isinstance(v, torch.Tensor) else v
                     for k, v in inputs.items()}
            text_features = self.model.get_text_features(**inputs)
            # Normalize to unit length
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            embedding = text_features.cpu().squeeze(0).tolist()

        return embedding


# Global singleton instance
@lru_cache(maxsize=1)
def get_siglip_embedder() -> SiglipEmbedder:
    """Get or create the singleton SigLIP embedder"""
    return SiglipEmbedder()
