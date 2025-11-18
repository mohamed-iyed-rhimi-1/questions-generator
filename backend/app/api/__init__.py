from fastapi import APIRouter
from app.api.videos import router as videos_router
from app.api.transcriptions import router as transcriptions_router
from app.api.questions import router as questions_router

# Create main API router with /api prefix
api_router = APIRouter(prefix="/api")

# Include videos router
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])

# Include transcriptions router
api_router.include_router(transcriptions_router, prefix="/transcriptions", tags=["transcriptions"])

# Include questions router
api_router.include_router(questions_router, prefix="/questions", tags=["questions"])
