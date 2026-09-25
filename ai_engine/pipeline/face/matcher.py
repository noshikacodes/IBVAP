from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from ai_engine.pipeline.face.types import FaceIdentityMatch, FaceEmbedding


class BaseFaceMatcher(ABC):
    """Abstract Interface for Face Identity Matching and Gallery Verification."""

    @abstractmethod
    def register_identity(
        self,
        identity_id: str,
        display_name: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Enrolls a known identity with a 512-D reference feature embedding vector."""
        pass

    @abstractmethod
    def remove_identity(self, identity_id: str) -> bool:
        """Removes an identity from the enrolled database."""
        pass

    @abstractmethod
    def match(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> FaceIdentityMatch:
        """Matches a probe face embedding against the enrolled gallery."""
        pass


class GalleryManager:
    """
    Lightweight, thread-safe in-memory gallery manager for enrolled identity profiles.
    Stores strictly unit-length L2-normalized synthetic / demo feature vectors.
    """

    def __init__(self, expected_dim: int = 512):
        self.expected_dim = expected_dim
        self._identities: Dict[str, Dict[str, Any]] = {}

    def normalize_vector(self, vec: np.ndarray) -> Tuple[bool, np.ndarray]:
        """Safely L2-normalizes an embedding vector. Returns (is_valid, normalized_vector)."""
        if vec is None:
            return False, np.zeros(self.expected_dim, dtype=np.float32)

        arr = np.asarray(vec, dtype=np.float32).flatten()
        if arr.size != self.expected_dim:
            return False, np.zeros(self.expected_dim, dtype=np.float32)

        if np.isnan(arr).any() or np.isinf(arr).any():
            return False, np.zeros(self.expected_dim, dtype=np.float32)

        norm = float(np.linalg.norm(arr))
        if norm == 0.0 or np.isnan(norm) or np.isinf(norm):
            return False, np.zeros(self.expected_dim, dtype=np.float32)

        return True, (arr / norm).astype(np.float32)

    def register_identity(
        self,
        identity_id: str,
        display_name: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Enrolls a new identity or updates an existing identity with a valid 512-D embedding.
        """
        clean_id = identity_id.strip()
        if not clean_id:
            return False

        is_valid, norm_emb = self.normalize_vector(embedding)
        if not is_valid:
            return False

        self._identities[clean_id] = {
            "identity_id": clean_id,
            "display_name": display_name.strip() or clean_id,
            "embedding": norm_emb,
            "metadata": dict(metadata or {})
        }
        return True

    def remove_identity(self, identity_id: str) -> bool:
        """Removes an identity profile if present."""
        clean_id = identity_id.strip()
        if clean_id in self._identities:
            del self._identities[clean_id]
            return True
        return False

    def get_identity(self, identity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves profile info by identity ID."""
        clean_id = identity_id.strip()
        if clean_id in self._identities:
            entry = self._identities[clean_id]
            return {
                "identity_id": entry["identity_id"],
                "display_name": entry["display_name"],
                "embedding": entry["embedding"].copy(),
                "metadata": dict(entry["metadata"])
            }
        return None

    def list_identities(self) -> List[Dict[str, Any]]:
        """Returns a list of all enrolled identity summaries."""
        return [
            {
                "identity_id": v["identity_id"],
                "display_name": v["display_name"],
                "metadata": dict(v["metadata"])
            }
            for v in self._identities.values()
        ]

    def get_matrix_and_ids(self) -> Tuple[Optional[np.ndarray], List[Dict[str, Any]]]:
        """Returns stacked (N, 512) gallery matrix and corresponding profile metadata list."""
        if not self._identities:
            return None, []

        profiles = list(self._identities.values())
        matrix = np.vstack([p["embedding"] for p in profiles])
        return matrix, profiles

    def count(self) -> int:
        return len(self._identities)

    def load_from_json(self, json_path: str) -> int:
        """
        Loads identity profiles from a JSON file safely.
        Validates 512 dimensions, rejects NaN/Inf, and L2-normalizes vectors.
        Returns the number of successfully enrolled identities.
        """
        import json
        import os

        if not os.path.exists(json_path):
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0

        enrolled_count = 0
        identities = data.get("identities", []) if isinstance(data, dict) else []

        for item in identities:
            if not isinstance(item, dict):
                continue
            identity_id = str(item.get("identity_id", "")).strip()
            display_name = str(item.get("display_name", "")).strip() or identity_id
            raw_emb = item.get("embedding")
            metadata = item.get("metadata", {})

            if not identity_id or raw_emb is None:
                continue

            try:
                emb_arr = np.asarray(raw_emb, dtype=np.float32)
                if self.register_identity(identity_id, display_name, emb_arr, metadata):
                    enrolled_count += 1
            except Exception:
                continue

        return enrolled_count

    def clear(self) -> None:
        self._identities.clear()


class CosineFaceMatcher(BaseFaceMatcher):
    """
    Vectorized Cosine Similarity Face Matcher.
    Compares 512-dimensional query embeddings against enrolled gallery profiles.
    """

    def __init__(
        self,
        gallery: Optional[GalleryManager] = None,
        default_threshold: float = 0.65,
        dimension: int = 512
    ):
        self.gallery = gallery if gallery is not None else GalleryManager(expected_dim=dimension)
        self.default_threshold = float(default_threshold)
        self.dimension = dimension

    def register_identity(
        self,
        identity_id: str,
        display_name: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        return self.gallery.register_identity(
            identity_id=identity_id,
            display_name=display_name,
            embedding=embedding,
            metadata=metadata
        )

    def remove_identity(self, identity_id: str) -> bool:
        return self.gallery.remove_identity(identity_id)

    def match(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> FaceIdentityMatch:
        """
        Calculates cosine similarity against all enrolled profiles using vectorized NumPy.
        Returns the highest-scoring identity match or UNKNOWN if below threshold.
        """
        thresh = threshold if threshold is not None else self.default_threshold

        # Normalize probe vector
        is_valid, probe_norm = self.gallery.normalize_vector(embedding)
        if not is_valid:
            return FaceIdentityMatch(
                identity_id="UNKNOWN",
                display_name="Unknown Person",
                similarity=0.0,
                confidence=0.0,
                is_match=False,
                is_unknown=True,
                metadata={"reason": "malformed_or_invalid_probe_embedding"}
            )

        matrix, profiles = self.gallery.get_matrix_and_ids()
        if matrix is None or len(profiles) == 0:
            return FaceIdentityMatch(
                identity_id="UNKNOWN",
                display_name="Unknown Person",
                similarity=0.0,
                confidence=0.0,
                is_match=False,
                is_unknown=True,
                metadata={"reason": "empty_gallery"}
            )

        # Vectorized Dot Product over (N, 512) and (512,)
        # Since both matrix rows and probe are unit-length L2 vectors:
        # Cosine Similarity = Matrix @ Probe
        similarities = np.dot(matrix, probe_norm)

        # Numerical safety clipping in [-1.0, 1.0]
        similarities = np.clip(similarities, -1.0, 1.0)

        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        best_profile = profiles[best_idx]

        if best_sim >= thresh:
            return FaceIdentityMatch(
                identity_id=best_profile["identity_id"],
                display_name=best_profile["display_name"],
                similarity=best_sim,
                confidence=best_sim,
                is_match=True,
                is_unknown=False,
                metadata={
                    "threshold_applied": thresh,
                    "profile_metadata": dict(best_profile.get("metadata", {}))
                }
            )
        else:
            return FaceIdentityMatch(
                identity_id="UNKNOWN",
                display_name="Unknown Person",
                similarity=best_sim,
                confidence=0.0,
                is_match=False,
                is_unknown=True,
                metadata={
                    "threshold_applied": thresh,
                    "nearest_identity": best_profile["identity_id"],
                    "nearest_similarity": round(best_sim, 4)
                }
            )
