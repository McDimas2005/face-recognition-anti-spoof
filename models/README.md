# Model Notes

This directory stores V1 model manifests, calibration defaults, and documentation for the pluggable inference layer.

## Included by Default

- `calibration-defaults.json`: conservative development thresholds

## Not Included

- no commercial face-recognition weights
- no production-certified anti-spoof model
- no pretrained artifacts should be assumed deployment-safe without separate licensing review

The demo provider in `apps/api/app/providers/demo.py` exists to keep the application runnable and swappable. It is not a production biometric claim.

