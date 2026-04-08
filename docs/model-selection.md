# Model Selection

## V1 runtime

The shipped code uses a demo provider abstraction:

- `FaceDetector`
- `FaceEmbedder`
- `LivenessScorer`
- `EmbeddingIndex`

## Why this is framed as demo-only

- current repo does not include production-safe commercial weights
- licensing provenance for public face models varies
- anti-spoof performance depends heavily on camera and environment validation

## Production path

Swap in ONNX-backed providers with approved model artifacts and recalibrate thresholds.

