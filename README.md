# Face Attendance Platform

Production-oriented attendance software built from a classroom face-recognition prototype into a full-stack system with enrollment workflows, browser-based live attendance, review tooling, audit logs, and containerized deployment.

## Overview

Face Attendance Platform is a rebuild of an earlier academic Computer Vision project, originally created as a simple face-recognition attendance prototype. The original version proved the concept. This version reframes the idea as a real software system: structured, multi-user, auditable, web-based, and designed to evolve toward production deployment.

The core use case is attendance tracking for classes, labs, events, or internal organizational check-ins where administrators want a faster and more structured process than manual roll call, spreadsheets, or badge-only workflows.

What makes this project different from a basic face-recognition demo is that attendance is not triggered by a single frame or a single weak prediction. The system separates enrollment from recognition, stores embeddings instead of training one model per user, applies quality and liveness gates, uses temporal consensus before committing attendance, prevents duplicates within a session, and sends ambiguous or suspicious cases to a review queue.

This repository is therefore not just “face recognition with a webcam.” It is a product-style software engineering exercise that combines AI workflow design, backend architecture, frontend admin UX, auditability, and deployment concerns in one codebase.

## Problem Statement

Attendance tracking sounds simple until it needs to be reliable, scalable, and reviewable.

Real-world teams and institutions often face a combination of problems:

- Manual attendance is slow and operationally expensive.
- Proxy attendance and informal fraud are easy when systems rely on verbal confirmation, unchecked sign-in sheets, or weak identity checks.
- Toy face-recognition demos are usually unreliable because they make decisions from one frame, assume one known face, and ignore unknown users, ambiguity, or spoofing risk.
- Many prototypes have no audit trail, making it difficult to investigate why attendance was marked or rejected.
- Enrollment and recognition are often blurred together, which creates poor data hygiene and inconsistent identity records.
- Deployment is frequently treated as an afterthought, leaving the system difficult to run outside a notebook or a single developer laptop.

This project addresses those problems with a more structured workflow:

- explicit person records
- explicit attendance sessions
- separate enrollment batches
- repeatable API-driven decisions
- review handling for unknown or suspicious attempts
- auditable logs for AI and manual actions

## Key Features

- **Browser webcam attendance**
  - The frontend captures frames from the browser and posts them to the backend for evaluation, avoiding the need for a dedicated kiosk client in V1.

- **Structured face enrollment workflow**
  - Administrators create a person record, open an enrollment batch, and upload multiple enrollment samples before the identity becomes recognition-ready.

- **Self-enrollment live capture for authenticated users**
  - A logged-in user can open `My Enrollment`, capture 100 live webcam photos for their owned identity, and replace their active enrollment set without using the admin upload flow.

- **Embedding-based recognition**
  - The system stores face embeddings and compares probe embeddings against a shared identity store instead of training one classifier per person.

- **Quality-gated enrollment and recognition**
  - Images are evaluated for face count, face size, blur, brightness, pose, and basic occlusion heuristics before being accepted.

- **Experimental quality-bypass mode**
  - Self-enrollment supports an explicitly labeled experimental mode that accepts low-quality single-face enrollment frames for testing. It still rejects empty, unreadable, and multi-face frames, and it is expected to reduce recognition reliability.

- **Passive liveness / anti-spoof gating**
  - A liveness score is computed before identity matching is allowed to progress. This reduces spoofing risk but is not presented as a guarantee.

- **Temporal multi-frame consensus**
  - Attendance is committed only after several accepted frames within a time window agree on identity and exceed configured thresholds.

- **Attendance session management**
  - Sessions have names, start and end times, late thresholds, and optional allowlists of permitted people.

- **Duplicate attendance prevention**
  - Once a person is marked present for a given session, later recognitions are logged as duplicates instead of creating new attendance events.

- **Unknown / ambiguous / suspicious review queue**
  - Unknown faces, ambiguous matches, spoof-rejected frames, and multi-face frames can be routed to a review queue for manual handling.

- **Admin dashboard**
  - The Next.js frontend includes views for users, people, enrollments, sessions, live attendance, logs, review queue, settings, and diagnostics.
  - The web app also includes `My Enrollment` for authenticated self-service enrollment replacement.

- **Audit logging**
  - Administrative actions and attendance decisions are recorded as audit logs, with manual overrides intentionally separated from AI-confirmed attendance.

- **Docker-based local deployment**
  - The repo includes Dockerfiles, Docker Compose, environment templates, and a reverse-proxy-friendly local stack.

- **Swappable model-provider design**
  - Detector, embedder, liveness scorer, and embedding index are abstracted behind provider interfaces so the current demo provider can later be replaced with stronger ONNX-based production models.

## How the System Works

The system is designed around a clear operational workflow rather than an ad hoc webcam loop.

### 1. An administrator creates people and users

- Admin users log into the web application.
- They create internal users for system access and create person records for the people who may attend sessions.
- People are the attendance identities; users are the authenticated application operators.

### 2. An administrator creates an attendance session

- A session represents a class, event, or check-in window.
- Each session has a name, start time, end time, late threshold, and optional allowlist of permitted people.

### 3. Enrollment samples are uploaded

- The admin opens an enrollment batch for a person.
- Enrollment samples are uploaded with diversity tags:
  - `frontal_neutral`
  - `left_yaw`
  - `right_yaw`
  - `expression`
  - `lighting`

### 4. Enrollment samples pass quality checks

- Each uploaded sample is evaluated for:
  - exactly one detected face
  - minimum face size
  - acceptable brightness range
  - blur threshold
  - frontal-pose tolerance
  - basic occlusion rejection

- The batch remains incomplete until at least five valid samples are accepted and all required diversity tags are covered.

### 4b. A user can replace their own enrollment with a live capture batch

- The `My Enrollment` page resolves or provisions exactly one owned `person` identity for the logged-in user.
- The browser opens the webcam, guides the user through a structured capture loop, and accepts frames until 100 enrollment photos are stored in the draft batch.
- The live enrollment UI shows the current face box, detector confidence, and quality score while capture is running.
- An explicitly labeled experimental bypass mode can skip soft quality heuristics for self-enrollment, but it still rejects zero-face, invalid-crop, and multi-face frames.
- The new batch stays inactive until the user explicitly confirms replacement.
- Finalization deactivates the previous active enrollment set, activates the new 100-photo set, and refreshes the active centroid embedding used by recognition.
- After replacement, the owned identity keeps at most 100 active enrollment photos for recognition use.

### 5. Embeddings are generated and stored

- Accepted enrollment images are converted into embeddings.
- Each accepted sample gets its own embedding.
- The backend also computes a centroid embedding for the person, which acts as a summary reference.

### 6. Live attendance starts in the browser

- The operator opens the live attendance page.
- The browser accesses the webcam using the MediaDevices API.
- Frames are sampled periodically and sent to the backend using a form-data request.

### 7. Recognition is evaluated frame by frame

For each submitted frame, the backend:

1. detects faces
2. rejects the frame if there are zero faces or multiple faces
3. evaluates quality gates on the detected face
4. runs passive liveness scoring
5. generates a probe embedding
6. compares it against stored person embeddings
7. ranks candidates by similarity

### 8. Temporal consensus decides whether attendance is committed

Even a good single-frame candidate is not enough.

The current policy requires repeated agreement over a rolling window:

- same top identity across multiple accepted frames
- similarity above threshold
- average similarity above commit threshold
- sufficient separation from the second-best candidate
- liveness above threshold

Only after those gates pass does the backend create an attendance event.

### 9. Duplicate and review logic are applied

- If the person is already marked for that session, the system returns `duplicate` and records the attempt without inserting a new attendance event.
- Unknown, ambiguous, spoof-rejected, or multi-face attempts can create review cases for manual follow-up.

### 10. Manual actions remain auditable

- AI-confirmed attendance uses `source = "ai_confirmed"`.
- Manual intervention uses `source = "manual_override"`.
- A manual override does not overwrite the original AI attempt; it creates separate auditable records.

## Recognition / AI Pipeline

This repository uses an embedding-based workflow because it scales better operationally than training one classifier per person.

### Face detection

The provider layer is designed to support stronger detector backends later. In the current codebase, the default shipped provider uses an OpenCV DNN SSD face detector backed by the legacy `res10_300x300_ssd_iter_140000.caffemodel` artifact when it is present in `legacy/DNN`.

If those assets are missing, the detector falls back to an OpenCV Haar cascade.

That means the architecture is production-oriented, but the shipped default detector is still a development/demo choice rather than a calibrated production deployment model.

### Alignment and preprocessing

The long-term design anticipates detection plus alignment, but the current default provider still performs a cropped-face flow without a dedicated landmark/alignment model.

The preprocessing path currently includes:

- padded face crop around the detected box
- grayscale normalization
- CLAHE contrast normalization
- Gaussian smoothing
- fixed-size resizing for descriptor generation

Quality heuristics are applied before recognition or enrollment acceptance.

### Embedding-based recognition

Accepted enrollment samples are converted into embeddings and stored in the database.

During recognition:

- the probe face is embedded
- that embedding is compared to stored sample embeddings and centroid embeddings
- exact cosine-style comparison logic is used
- candidate ranking is aggregated per person
- the best sample score and best centroid score are blended into a final per-person score

Why this is preferable to a per-user classifier:

- new people can be enrolled without retraining a classifier
- one global identity store is easier to maintain
- open-set handling becomes more natural
- thresholds and review workflows are easier to express

### Current shipped demo provider

The repo currently ships with a stronger demo provider than the original prototype stack:

| Component | Current shipped implementation | Notes |
| --- | --- | --- |
| Face detector | `demo-opencv-dnn-ssd` | Uses OpenCV DNN SSD from `legacy/DNN`, with Haar fallback |
| Primary embedder | `demo-robust-handcrafted-embedder` | Handcrafted descriptor using LBP-style histograms, HOG, coarse grayscale, and gradient histograms |
| Legacy embedder support | `demo-histogram-embedder` | Kept for compatibility with older enrollments already stored in the database |
| Liveness scorer | `demo-heuristic-liveness` | Heuristic passive score, not production anti-spoof |
| Matching index | `exact-cosine` | In-process exact similarity scoring |

This improves the shipped default behavior, but it is still not equivalent to a modern pretrained ArcFace / RetinaFace-style stack.

### Liveness / anti-spoof gating

The default liveness implementation is heuristic and demo-grade. It exists to preserve the application flow and the provider abstraction.

Important: this repository does **not** claim that the current shipped liveness implementation is enough for real-world spoof resistance. It should be treated as a placeholder that reduces risk in demos and development, not as a final production anti-spoofing system.

### Temporal consensus

Attendance is only marked after repeated consistency across multiple frames inside a rolling window. This is one of the most important distinctions between this project and a weak webcam demo.

### Thresholds and open-set handling

The backend exposes configurable settings for:

- similarity threshold
- commit threshold
- ambiguity margin
- liveness threshold
- consensus frame count
- consensus window duration
- minimum face size
- minimum brightness
- maximum brightness
- minimum blur score
- maximum yaw score
- maximum occlusion score

Super Admin users can adjust all recognition and quality thresholds from the settings page. Admin users remain limited to the non-superadmin settings sections.

If the top candidate is too weak, the result becomes `unknown`. If the top and second-best candidates are too close, the result becomes `ambiguous`.

### Current default thresholds and scores

The current development/demo defaults are stored in `models/calibration-defaults.json` and mirrored in the API settings.

| Setting | Current default | Meaning |
| --- | --- | --- |
| Similarity threshold | `0.58` | Minimum top-person score required before a frame can leave `unknown` |
| Commit threshold | `0.62` | Minimum average similarity across the consensus window before attendance is committed |
| Ambiguity margin | `0.02` | Minimum separation required between the top and second-best candidate |
| Liveness threshold | `0.28` | Minimum passive liveness score required before matching is allowed to continue |
| Consensus frames | `3` | Number of accepted frames needed in the rolling window |
| Consensus window | `5` seconds | Rolling time window used for temporal consensus |
| Minimum face size | `80` | Smallest accepted face crop edge length |
| Minimum brightness | `28.0` | Lower bound of accepted average grayscale brightness |
| Maximum brightness | `225.0` | Upper bound of accepted average grayscale brightness |
| Minimum blur score | `110.0` | Minimum Laplacian variance used as the blur gate |
| Maximum yaw score | `0.5` | Maximum left/right brightness asymmetry tolerated before pose rejection |
| Maximum occlusion score | `0.55` | Maximum top/bottom brightness asymmetry tolerated before occlusion rejection |

Important implementation detail:

- `top_score` is the final aggregated person score used for decision-making.
- That score blends sample and centroid evidence as `0.7 * best_sample_similarity + 0.3 * best_centroid_similarity`.
- `second_score` is the same aggregated value for the second-ranked person.
- `margin` is `top_score - second_score`.
- `match_percent` is a UI-friendly rendering of `top_score * 100`.
- `quality_score` is a normalized helper score in the range `0.0` to `1.0` built from face size, blur, brightness, pose, and occlusion heuristics.
- The current quality-score weighting is `0.20 face_size + 0.30 blur + 0.20 brightness + 0.15 yaw + 0.15 occlusion`.
- `detector_confidence` is the face detector’s box confidence for the selected face.

The `quality_score` is not itself the hard acceptance gate. The hard gate still comes from the individual checks for face count, face size, brightness, blur, pose, and occlusion.

### What is logged for each recognition attempt

Each recognition attempt stores a structured `breakdown` payload. New attempts include the raw numbers needed to inspect why a frame was accepted, rejected, kept as a candidate, or marked unknown.

The current breakdown typically includes:

- human-readable message such as `Unknown face`, `Identity margin too small`, or `Attendance committed`
- `face_box` coordinates and source image dimensions
- `detector_confidence`
- `blur_score`
- `brightness`
- `yaw_score`
- `occlusion_score`
- `quality_score`
- `top_person_name`
- `top_score_raw`
- `second_person_id`
- `second_person_name`
- `second_score_raw`
- `margin_raw`
- `match_percent`
- `top_model_name`
- `candidate_scores` for the top ranked candidates
- `recognition_thresholds`
- `quality_thresholds`
- `matching_frames` and `average_similarity` when temporal consensus is in progress or attendance is committed

In addition to the `breakdown`, the recognition-attempt record itself stores:

- `face_count`
- `quality_passed`
- `liveness_score`
- `top_person_id`
- `top_score`
- `second_score`
- final `outcome`

This data is exposed in the Logs page and in the live decision breakdown panel so operators can see both the decision and the numbers behind it.

### Demo model mode vs production-safe model mode

This repository intentionally separates **architecture** from **model maturity**.

- The current code ships with a runnable demo provider.
- The provider interfaces are designed so stronger ONNX-based detector, embedder, and anti-spoof models can replace the demo backend.
- Public demo weights are not automatically production-safe from either a performance or licensing perspective.

If you plan to deploy this beyond development, you should treat model onboarding, calibration, and licensing review as explicit product work.

## Tech Stack

### Frontend

- **Next.js (App Router)**
  - Used for the admin-facing web application and browser-based attendance interface.
- **React + TypeScript**
  - Provides typed UI development and a maintainable client-side state model.
- **Tailwind CSS**
  - Used for rapid, consistent styling of the dashboard and operator workflows.

### Backend

- **FastAPI**
  - Chosen for typed request/response models, clear API structure, automatic docs, and strong fit for service-style Python backends.
- **SQLAlchemy 2.0**
  - Used as the ORM for persistence and domain modeling.
- **Alembic**
  - Included for database schema versioning and repeatable migrations.
- **JWT authentication**
  - Supports access and refresh tokens for authenticated admin workflows.
- **Simple RBAC**
  - Roles include `superadmin`, `admin`, `reviewer`, and `viewer`.

### Database

- **PostgreSQL 16**
  - The primary operational database for users, persons, sessions, embeddings, review cases, and audit logs.

### AI / inference

- **Provider abstraction**
  - The code separates `FaceDetector`, `FaceEmbedder`, `LivenessScorer`, and `EmbeddingIndex`.
- **NumPy + OpenCV + Pillow**
  - Used in the current demo provider and image preprocessing path.
- **Exact in-process matching**
  - V1 uses exact similarity scoring instead of FAISS to keep the initial implementation simple.

### Deployment / infrastructure

- **Docker Compose**
  - Provides a local multi-service stack with API, web app, Postgres, and Caddy.
- **Caddy**
  - Included as a reverse-proxy-friendly frontend for local composition.

### Dev tooling

- **Pytest**
  - Used for backend tests.
- **TypeScript build tooling**
  - Supports the web application and shared package.
- **Makefile**
  - Simplifies common local development commands.

## Architecture

At a high level, the application is a full-stack web system with a clear separation between UI, API, persistence, and inference logic.

### Architecture components

- **Web frontend**
  - Handles login, admin operations, webcam capture, operator feedback, and review workflows.
- **API service**
  - Owns business logic, auth, session rules, enrollment validation, recognition decisions, audit logging, and review-case creation.
- **Database**
  - Stores users, persons, enrollment batches, embeddings, sessions, recognition attempts, attendance events, settings, and audit logs.
- **File storage**
  - Uses local disk storage in V1 for optionally retained enrollment or review images.
- **Inference provider layer**
  - Encapsulates the detector, embedder, liveness scorer, and matching strategy.
- **Review and admin flow**
  - Suspicious or unresolved recognition outcomes are surfaced for manual inspection.

### Text-based architecture diagram

```text
+---------------------------+
| Next.js Admin Frontend    |
| - login                   |
| - people/enrollments      |
| - sessions                |
| - live attendance         |
| - logs/review/settings    |
+-------------+-------------+
              |
              | HTTP / JSON / multipart form-data
              v
+---------------------------+
| FastAPI Backend           |
| - auth + RBAC             |
| - enrollment logic        |
| - attendance sessions     |
| - recognition policy      |
| - review queue            |
| - audit logging           |
+------+------+-------------+
       |      |
       |      +-----------------------------+
       |                                    |
       v                                    v
+-------------+                 +------------------------+
| PostgreSQL  |                 | Local File Storage     |
| - users     |                 | - optional snapshots   |
| - persons   |                 | - optional enrollment  |
| - embeddings|                 +------------------------+
| - sessions  |
| - attempts  |
| - events    |
| - reviews   |
| - audit     |
+-------------+
       |
       v
+---------------------------+
| Provider Layer            |
| - FaceDetector            |
| - FaceEmbedder            |
| - LivenessScorer          |
| - EmbeddingIndex          |
+---------------------------+
```

## Project Structure

```text
apps/
  api/        FastAPI backend, domain model, routes, services, tests, migrations
  web/        Next.js frontend and browser-based attendance UI
packages/
  shared/     Shared TypeScript constants and types
models/       Calibration defaults and model-related notes
scripts/      Helper scripts for local bootstrap and future tooling
docs/         Architecture, deployment, privacy, calibration, and API docs
infra/        Reverse proxy and infrastructure assets
legacy/       Preserved academic prototype and historical model assets
```

### Directory guide

- `apps/api`
  - Main backend application.
  - Contains routes for auth, users, people, enrollments, sessions, recognition, review cases, settings, and health.

- `apps/web`
  - Next.js admin interface.
  - Contains pages for dashboard, login, users, people, enrollments, sessions, live attendance, logs, review queue, settings, and diagnostics.

- `packages/shared`
  - Small shared package for frontend-side enums and shared constants.

- `models`
  - Calibration defaults and notes about model maturity and licensing expectations.

- `scripts`
  - Helper scripts such as local bootstrap.

- `docs`
  - Supplemental project documentation for setup, architecture, model selection, privacy, calibration, deployment, and roadmap.

- `infra`
  - Reverse proxy configuration and deployment-adjacent assets.

- `legacy`
  - Archived Flask/TensorFlow prototype and historical files from the academic version of the project.

## Running the Project

This repository supports a full Docker Compose workflow and an optional local development workflow.

### Prerequisites

For the full local stack:

- Docker Desktop or Docker Engine
- Docker Compose

For local non-container development:

- Python 3.12
- Node.js 20+
- npm
- PostgreSQL 16
- `python3.12-venv` on Debian/Ubuntu-based systems if you want to create a virtual environment locally

### 1. Configure environment variables

Copy the environment template:

```bash
cp .env.example .env
```

Important values in `.env`:

- `API_DATABASE_URL`
- `API_SECRET_KEY`
- `API_BOOTSTRAP_ADMIN_EMAIL`
- `API_BOOTSTRAP_ADMIN_PASSWORD`
- `NEXT_PUBLIC_API_BASE_URL`

### 2. Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`
- Caddy proxy: `http://localhost`

Default seeded admin credentials:

- Email: `admin@example.com`
- Password: `ChangeMe123!`

To stop the stack:

```bash
docker compose down
```

To remove volumes and reset the local database:

```bash
docker compose down -v
```

### 3. Optional local development workflow

If you prefer to run API and web locally while using Postgres directly:

Start Postgres first and update `.env` accordingly, for example:

```env
API_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/attendance
API_STORAGE_PATH=apps/api/data
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Install and run the API:

```bash
sudo apt install -y python3.12-venv   # Debian/Ubuntu if needed
make api-install
cd apps/api
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal, install and run the web app:

```bash
npm install
npm run dev:web
```

### 4. Useful commands

```bash
make api-install
make web-install
make api-dev
make web-dev
make test
make lint
make compose-up
make compose-down
```

## First-Run Workflow

After the system starts, a good first-run path is:

1. Open the web app and sign in with the seeded admin credentials.
2. Go to **People** and create a person record.
3. Go to **Enrollments** and create an enrollment batch for that person.
4. Upload at least five enrollment images, covering all required diversity tags.
5. Go to **Sessions** and create an attendance session.
6. Optionally restrict the session using the allowlist.
7. Go to **Live Attendance** and select the session.
8. Start the webcam capture loop.
9. Watch the recognition state and decision breakdown.
10. Review any unknown, ambiguous, spoof-rejected, or multi-face outcomes in **Review Queue**.

## Core Workflows

### Enrollment Workflow

- Create a person.
- Open an enrollment batch.
- Upload tagged samples.
- Each sample is validated for face count and quality.
- Accepted samples generate embeddings.
- A centroid embedding is recalculated as the person’s enrollment set grows.
- The batch becomes ready only when minimum sample count and diversity coverage are satisfied.

### Attendance Workflow

- Create or open an active attendance session.
- Start webcam capture in the browser.
- Frames are sent to the backend.
- The backend evaluates face count, quality, liveness, embedding match, and temporal consistency.
- The operator sees the detected face box, current recognition state, current scores, and the recognized user name when a face is matched.
- If the policy passes, an attendance event is created.
- If the person is already marked present, the system records a duplicate attempt instead.

### Review Workflow

- Unknown faces, ambiguous matches, spoof-rejected frames, and multiple-face frames can generate review cases.
- Reviewers can inspect these cases and resolve them.
- Manual marking creates a `manual_override` attendance event instead of pretending the AI match succeeded.

### Admin Workflow

- Manage users and roles.
- Manage people and enrollment readiness.
- Create sessions and define attendance windows.
- Review logs, recognition attempts, attendance events, and review cases.
- Inspect detailed per-attempt breakdowns including thresholds, raw scores, and top candidate information.
- Adjust thresholds and retention-related settings from the settings page.

## Security, Privacy, and Responsible Use

This project handles biometric-like identity data and should be treated accordingly.

Key considerations:

- **Embeddings are sensitive**
  - Even when raw images are not stored, facial embeddings and attendance metadata still deserve careful handling.

- **Raw image retention should be limited**
  - V1 supports policy-controlled image retention. Enrollment image retention is off by default in the environment template. Review-image retention is configurable.

- **Demo mode is not production readiness**
  - The current shipped detector, embedder, and liveness scorer are demonstration-oriented implementations designed to keep the platform runnable and swappable.

- **Anti-spoofing is risk reduction, not a guarantee**
  - The current system reduces spoofing risk with passive checks and policy gates, but it does not guarantee protection against printed-photo attacks, replay attacks, or more sophisticated presentation attacks.

- **Consent and compliance matter**
  - Real deployment should include informed consent, retention policy, access controls, legal review, and alignment with institutional or organizational policy.

- **Admin actions are auditable**
  - The system separates AI-confirmed attendance from manual overrides and stores audit logs for operational traceability.

## Current Status

This repository is best described as:

- **production-oriented in architecture**
- **development/demo ready in implementation**
- **still evolving in model maturity and operational hardening**

The application already includes a real full-stack structure, domain model, admin UX, review flow, audit logging, and containerized deployment. However, the default shipped vision provider is intentionally demo-grade. A real rollout would still require calibrated and appropriately licensed models, stronger validation, and deployment hardening.

## Limitations

The current implementation is intentionally honest about its boundaries.

- The default AI provider is demo-grade:
  - OpenCV DNN SSD detection with legacy asset dependency and Haar fallback
  - handcrafted embeddings rather than a modern pretrained face-recognition network
  - heuristic liveness scoring

- Face alignment is not yet implemented with a dedicated production detector/alignment stack.

- Accuracy and liveness behavior will be highly environment-dependent.

- The system does not guarantee protection against all spoofing methods.

- Thresholds are configurable, but production calibration is still required.

- Older databases may temporarily contain mixed embedding families from previous demo providers. The current code handles those safely, but the best operational result still comes from re-enrolling after provider upgrades.

- V1 uses local file storage rather than a cloud object storage adapter.

- V1 assumes a single-tenant operational shape.

- The current frontend and backend are functional, but still closer to an early product implementation than a hardened enterprise release.

- Docker and full runtime validation depend on local machine setup; this repository has been structured for containerized use, but environment readiness still matters.

## Roadmap

Planned or likely next steps include:

- stronger ONNX-backed detector and embedder providers
- stronger anti-spoof model integration
- explicit face alignment support
- calibration tooling and evaluation workflows
- richer session analytics and reporting
- kiosk mode or dedicated attendance terminal support
- mobile-friendly operator workflows
- SSO and organization-level identity support
- cloud storage integration
- production model onboarding with clearer artifact management
- more advanced observability and operational metrics

## Why This Project Is Interesting

This project is technically interesting because it sits at the intersection of multiple engineering disciplines:

- computer vision and AI inference workflows
- backend API design and persistence modeling
- frontend admin tooling and operator UX
- security and privacy-aware application design
- infrastructure and containerized deployment

It is also a strong example of turning a classroom prototype into a product-style system. Instead of stopping at a webcam demo, the repository addresses identity lifecycle, review operations, auditability, and deployment ergonomics. That makes it a useful portfolio project for anyone interested in applied AI systems, full-stack product engineering, or real-world CV workflow design.

## License / Usage Note

This repository is licensed under the [MIT License](/home/mcdimas/projects/face-recognition-anti-spoof/LICENSE).

Important usage note:

- The repository license covers the software in this repo.
- Model weights, pretrained artifacts, example datasets, or legacy assets may have separate licensing constraints.
- The presence of demo-grade or historical model assets in the project history does **not** imply commercial deployment rights.
- Before any real production use, verify the licensing status of all model artifacts and the legal basis for any biometric data processing.
