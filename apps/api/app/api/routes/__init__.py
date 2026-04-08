from fastapi import APIRouter

from app.api.routes import attendance, auth, enrollments, health, persons, recognition, recognition_attempts, review_cases, sessions, settings, users

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(persons.router, prefix="/persons", tags=["persons"])
router.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(recognition.router, prefix="/recognition", tags=["recognition"])
router.include_router(attendance.router, prefix="/attendance-events", tags=["attendance"])
router.include_router(recognition_attempts.router, prefix="/recognition-attempts", tags=["recognition"])
router.include_router(review_cases.router, prefix="/review-cases", tags=["review"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
