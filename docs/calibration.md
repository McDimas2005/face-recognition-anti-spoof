# Calibration

V1 ships with conservative development defaults in `models/calibration-defaults.json`.

Before production attendance writes are trusted, calibrate using held-out data:

- threshold sweep for FAR / FRR
- open-set rejection checks
- multi-frame consensus sensitivity
- per-identity false-match inspection

The demo provider is not sufficient evidence for production calibration claims.

