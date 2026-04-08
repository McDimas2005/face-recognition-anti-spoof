from __future__ import annotations

import math

import cv2
import numpy as np

from app.core.config import settings
from app.providers.base import EmbeddingIndex, FaceBox, FaceDetector, FaceEmbedder, LivenessScorer


class OpenCvHaarFaceDetector(FaceDetector):
    name = "demo-opencv-haar"

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.classifier = cv2.CascadeClassifier(cascade_path)

    def detect(self, image: np.ndarray) -> list[FaceBox]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detections = self.classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
        return [FaceBox(int(x), int(y), int(w), int(h), 0.8) for x, y, w, h in detections]


class HistogramEmbedder(FaceEmbedder):
    name = "demo-histogram-embedder"

    def embed(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        vector = resized.astype(np.float32).flatten()
        vector = vector - np.mean(vector)
        norm = np.linalg.norm(vector) or 1.0
        return vector / norm


class HeuristicLivenessScorer(LivenessScorer):
    name = "demo-heuristic-liveness"

    def score(self, image: np.ndarray) -> float:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        contrast = float(np.std(gray))
        value = min(1.0, (lap_var / 250.0) * 0.6 + (contrast / 64.0) * 0.4)
        return max(0.0, value)


class CosineEmbeddingIndex(EmbeddingIndex):
    name = "exact-cosine"

    def score(self, probe: np.ndarray, candidates: list[tuple[str, np.ndarray, bool]]) -> list[dict]:
        results = []
        for person_id, candidate, is_centroid in candidates:
            similarity = float(np.dot(probe, candidate))
            results.append({"person_id": person_id, "similarity": similarity, "is_centroid": is_centroid})
        return sorted(results, key=lambda item: item["similarity"], reverse=True)


def crop_face(image: np.ndarray, box: FaceBox) -> np.ndarray:
    x0 = max(0, box.x)
    y0 = max(0, box.y)
    x1 = min(image.shape[1], box.x + box.width)
    y1 = min(image.shape[0], box.y + box.height)
    return image[y0:y1, x0:x1]


def assess_quality(image: np.ndarray, box: FaceBox) -> dict:
    face = crop_face(image, box)
    if face.size == 0:
        return {"passed": False, "reason": "invalid_crop", "face_size": 0}

    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    face_size = min(face.shape[:2])
    left_half = float(np.mean(gray[:, : gray.shape[1] // 2])) if gray.shape[1] > 1 else brightness
    right_half = float(np.mean(gray[:, gray.shape[1] // 2 :])) if gray.shape[1] > 1 else brightness
    yaw_score = abs(left_half - right_half) / max(1.0, brightness)
    lower_slice = gray[gray.shape[0] // 2 :, :]
    upper_slice = gray[: gray.shape[0] // 2, :]
    occlusion_score = abs(float(np.mean(lower_slice)) - float(np.mean(upper_slice))) / max(1.0, brightness)

    passed = True
    reason = None
    if face_size < settings.min_face_size:
        passed = False
        reason = "face_too_small"
    elif brightness < settings.min_brightness or brightness > settings.max_brightness:
        passed = False
        reason = "brightness_out_of_range"
    elif blur_score < settings.max_blur_score:
        passed = False
        reason = "image_too_blurry"
    elif yaw_score > settings.max_yaw_score:
        passed = False
        reason = "pose_not_frontal_enough"
    elif occlusion_score > settings.max_occlusion_score:
        passed = False
        reason = "possible_occlusion"

    return {
        "passed": passed,
        "reason": reason,
        "face_size": face_size,
        "blur_score": blur_score,
        "brightness": brightness,
        "yaw_score": yaw_score,
        "occlusion_score": occlusion_score,
    }


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    norm_left = np.linalg.norm(left) or 1.0
    norm_right = np.linalg.norm(right) or 1.0
    return float(np.dot(left, right) / (norm_left * norm_right))


detector = OpenCvHaarFaceDetector()
embedder = HistogramEmbedder()
liveness = HeuristicLivenessScorer()
index = CosineEmbeddingIndex()

