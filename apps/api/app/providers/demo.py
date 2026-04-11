from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.providers.base import EmbeddingIndex, FaceBox, FaceDetector, FaceEmbedder, LivenessScorer


def _default_quality_policy() -> dict:
    return {
        "min_face_size": int(settings.min_face_size),
        "min_brightness": float(settings.min_brightness),
        "max_brightness": float(settings.max_brightness),
        "blur_threshold": float(settings.max_blur_score),
        "max_yaw_score": float(settings.max_yaw_score),
        "max_occlusion_score": float(settings.max_occlusion_score),
    }


def _locate_asset(*parts: str) -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent.joinpath(*parts)
        if candidate.exists():
            return candidate
    return None


class OpenCvHaarFaceDetector(FaceDetector):
    name = "demo-opencv-haar"

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.classifier = cv2.CascadeClassifier(cascade_path)

    def detect(self, image: np.ndarray) -> list[FaceBox]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detections = self.classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
        return [FaceBox(int(x), int(y), int(w), int(h), 0.75) for x, y, w, h in detections]


class OpenCvDnnFaceDetector(FaceDetector):
    name = "demo-opencv-dnn-ssd"

    def __init__(self) -> None:
        self.fallback = OpenCvHaarFaceDetector()
        proto = _locate_asset("legacy", "DNN", "deploy.prototxt")
        model = _locate_asset("legacy", "DNN", "res10_300x300_ssd_iter_140000.caffemodel")
        self.net = None
        if proto and model:
            self.net = cv2.dnn.readNetFromCaffe(str(proto), str(model))

    def detect(self, image: np.ndarray) -> list[FaceBox]:
        if self.net is None:
            return self.fallback.detect(image)

        height, width = image.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.net.setInput(blob)
        raw = self.net.forward()

        boxes: list[list[int]] = []
        confidences: list[float] = []
        for index in range(raw.shape[2]):
            confidence = float(raw[0, 0, index, 2])
            if confidence < 0.55:
                continue
            start_x, start_y, end_x, end_y = raw[0, 0, index, 3:7] * np.array([width, height, width, height])
            x0 = max(0, int(start_x))
            y0 = max(0, int(start_y))
            x1 = min(width, int(end_x))
            y1 = min(height, int(end_y))
            box_width = max(0, x1 - x0)
            box_height = max(0, y1 - y0)
            if box_width == 0 or box_height == 0:
                continue
            boxes.append([x0, y0, box_width, box_height])
            confidences.append(confidence)

        if not boxes:
            return self.fallback.detect(image)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.55, 0.3)
        if len(indices) == 0:
            return self.fallback.detect(image)

        detections: list[FaceBox] = []
        for idx in np.array(indices).flatten():
            x, y, box_width, box_height = boxes[int(idx)]
            detections.append(FaceBox(x, y, box_width, box_height, confidences[int(idx)]))
        return sorted(detections, key=lambda item: item.confidence, reverse=True)


class LegacyHistogramEmbedder(FaceEmbedder):
    name = "demo-histogram-embedder"

    def embed(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        vector = resized.astype(np.float32).flatten()
        vector = vector - np.mean(vector)
        norm = np.linalg.norm(vector) or 1.0
        return vector / norm


class RobustHandcraftedEmbedder(FaceEmbedder):
    name = "demo-robust-handcrafted-embedder"

    def __init__(self) -> None:
        self.hog = cv2.HOGDescriptor((64, 64), (16, 16), (8, 8), (8, 8), 9)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        normalized = self.clahe.apply(resized)
        return cv2.GaussianBlur(normalized, (3, 3), 0)

    def _lbp(self, gray: np.ndarray) -> np.ndarray:
        center = gray[1:-1, 1:-1]
        codes = np.zeros_like(center, dtype=np.uint8)
        neighbors = [
            gray[:-2, :-2],
            gray[:-2, 1:-1],
            gray[:-2, 2:],
            gray[1:-1, 2:],
            gray[2:, 2:],
            gray[2:, 1:-1],
            gray[2:, :-2],
            gray[1:-1, :-2],
        ]
        for bit, neighbor in enumerate(neighbors):
            codes |= ((neighbor >= center).astype(np.uint8) << bit)
        return codes

    def _grid_histogram(self, image: np.ndarray, *, bins: int, grid: tuple[int, int]) -> np.ndarray:
        rows, cols = grid
        cell_height = image.shape[0] // rows
        cell_width = image.shape[1] // cols
        features = []
        for row in range(rows):
            for col in range(cols):
                y0 = row * cell_height
                y1 = image.shape[0] if row == rows - 1 else (row + 1) * cell_height
                x0 = col * cell_width
                x1 = image.shape[1] if col == cols - 1 else (col + 1) * cell_width
                cell = image[y0:y1, x0:x1]
                hist = cv2.calcHist([cell], [0], None, [bins], [0, 256]).astype(np.float32).flatten()
                hist /= float(hist.sum() or 1.0)
                features.append(hist)
        return np.concatenate(features, axis=0)

    def embed(self, image: np.ndarray) -> np.ndarray:
        normalized = self._preprocess(image)
        lbp = self._lbp(normalized)
        lbp_hist = self._grid_histogram((lbp // 8).astype(np.uint8), bins=32, grid=(4, 4))

        hog_ready = cv2.resize(normalized, (64, 64), interpolation=cv2.INTER_AREA)
        hog = self.hog.compute(hog_ready).astype(np.float32).flatten()
        hog /= float(np.linalg.norm(hog) or 1.0)

        coarse = cv2.resize(normalized, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32).flatten() / 255.0
        coarse = coarse - np.mean(coarse)
        coarse /= float(np.linalg.norm(coarse) or 1.0)

        gradient_x = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(gradient_x, gradient_y)
        magnitude_u8 = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        gradient_hist = cv2.calcHist([magnitude_u8], [0], None, [32], [0, 256]).astype(np.float32).flatten()
        gradient_hist /= float(gradient_hist.sum() or 1.0)

        vector = np.concatenate([lbp_hist, hog, coarse, gradient_hist], axis=0)
        vector = vector.astype(np.float32)
        vector /= float(np.linalg.norm(vector) or 1.0)
        return vector


class HeuristicLivenessScorer(LivenessScorer):
    name = "demo-heuristic-liveness"

    def score(self, image: np.ndarray) -> float:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        contrast = float(np.std(gray))
        value = min(1.0, (lap_var / 220.0) * 0.55 + (contrast / 58.0) * 0.45)
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
    pad_x = int(box.width * 0.12)
    pad_y = int(box.height * 0.18)
    x0 = max(0, box.x - pad_x)
    y0 = max(0, box.y - pad_y)
    x1 = min(image.shape[1], box.x + box.width + pad_x)
    y1 = min(image.shape[0], box.y + box.height + pad_y)
    return image[y0:y1, x0:x1]


def assess_quality(image: np.ndarray, box: FaceBox, quality_policy: dict | None = None) -> dict:
    policy = {**_default_quality_policy(), **(quality_policy or {})}
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
    if face_size < policy["min_face_size"]:
        passed = False
        reason = "face_too_small"
    elif brightness < policy["min_brightness"] or brightness > policy["max_brightness"]:
        passed = False
        reason = "brightness_out_of_range"
    elif blur_score < policy["blur_threshold"]:
        passed = False
        reason = "image_too_blurry"
    elif yaw_score > policy["max_yaw_score"]:
        passed = False
        reason = "pose_not_frontal_enough"
    elif occlusion_score > policy["max_occlusion_score"]:
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


detector = OpenCvDnnFaceDetector()
embedder = RobustHandcraftedEmbedder()
legacy_embedder = LegacyHistogramEmbedder()
supported_embedders = {
    embedder.name: embedder,
    legacy_embedder.name: legacy_embedder,
}
liveness = HeuristicLivenessScorer()
index = CosineEmbeddingIndex()
