# API

## Auth

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

## Core resources

- `GET|POST|PATCH /api/users`
- `GET|POST|PATCH /api/persons`
- `GET /api/me/enrollment/live`
- `POST /api/me/enrollment/live/start`
- `POST /api/me/enrollment/live/frame`
- `POST /api/me/enrollment/live/finalize`
- `DELETE /api/me/enrollment/live/samples/{sample_id}`
- `POST /api/enrollments/batches`
- `GET /api/enrollments/batches/{batch_id}`
- `POST /api/enrollments/batches/{batch_id}/samples`
- `GET|POST|PATCH /api/sessions`
- `POST /api/recognition/evaluate`
- `GET /api/attendance-events`
- `GET /api/recognition-attempts`
- `GET /api/review-cases`
- `POST /api/review-cases/{review_id}/resolve`
- `GET|PUT /api/settings`
- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /api/health/metrics`
