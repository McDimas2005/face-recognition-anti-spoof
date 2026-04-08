from dataclasses import dataclass

import numpy as np


@dataclass
class FaceBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class QualityReport:
    passed: bool
    blur_score: float
    brightness: float
    yaw_score: float
    occlusion_score: float
    face_size: int
    reason: str | None = None


class FaceDetector:
    name = "base-detector"

    def detect(self, image: np.ndarray) -> list[FaceBox]:
        raise NotImplementedError


class FaceEmbedder:
    name = "base-embedder"

    def embed(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class LivenessScorer:
    name = "base-liveness"

    def score(self, image: np.ndarray) -> float:
        raise NotImplementedError


class EmbeddingIndex:
    name = "base-index"

    def score(self, probe: np.ndarray, candidates: list[tuple[str, np.ndarray, bool]]) -> list[dict]:
        raise NotImplementedError

