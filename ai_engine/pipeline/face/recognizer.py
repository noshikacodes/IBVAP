import os
import logging
from typing import Optional
import numpy as np
import cv2

from ai_engine.pipeline.interfaces import BaseFaceRecognizer

logger = logging.getLogger("ibvap.face.recognizer")


class FaceRecognizer(BaseFaceRecognizer):
    """
    Lightweight CPU-optimized Face Feature Recognizer implementing BaseFaceRecognizer.
    Uses MobileFaceNet + ArcFace ONNX to extract 512-dimensional L2-normalized embeddings.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        embedding_dimension: int = 512
    ):
        self.device = device
        self.embedding_dimension = embedding_dimension
        self.net = None
        self.model_path = model_path

        if model_path:
            self.load_model(model_path, device=device)

    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes the MobileFaceNet ArcFace ONNX model."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Face recognizer model file not found: {model_path}")

        try:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.device = device
            self.model_path = model_path
            logger.info(f"Loaded MobileFaceNet ArcFace ONNX model from {model_path} via OpenCV DNN")
        except Exception as e:
            logger.error(f"Failed to load MobileFaceNet ArcFace ONNX model from {model_path}: {e}")
            raise RuntimeError(f"Failed to initialize FaceRecognizer: {e}")

    def compute_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Extracts a 512-dimensional L2-normalized feature embedding vector from a cropped face image.
        Returns np.ndarray of shape (512,) and dtype float32.
        """
        if face_crop is None or face_crop.size == 0:
            return np.zeros(self.embedding_dimension, dtype=np.float32)

        if self.net is None:
            raise RuntimeError("FaceRecognizer model is not loaded. Call load_model() first.")

        try:
            # Preprocess face crop for MobileFaceNet: (112, 112), normalized to [-1, 1]
            blob = cv2.dnn.blobFromImage(
                face_crop,
                scalefactor=1.0 / 127.5,
                size=(112, 112),
                mean=(127.5, 127.5, 127.5),
                swapRB=True,
                crop=False
            )
            self.net.setInput(blob)
            raw_out = self.net.forward()
            emb = np.asarray(raw_out, dtype=np.float32).flatten()

            if emb.size != self.embedding_dimension:
                logger.warning(
                    f"Unexpected embedding size from model: expected {self.embedding_dimension}, got {emb.size}"
                )
                return np.zeros(self.embedding_dimension, dtype=np.float32)

            # L2-normalize embedding vector
            norm = float(np.linalg.norm(emb))
            if norm == 0.0 or np.isnan(norm) or np.isinf(norm):
                return np.zeros(self.embedding_dimension, dtype=np.float32)

            norm_emb = (emb / norm).astype(np.float32)
            return norm_emb

        except Exception as e:
            logger.warning(f"Error extracting face embedding: {e}")
            return np.zeros(self.embedding_dimension, dtype=np.float32)
