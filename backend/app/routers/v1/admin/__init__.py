from fastapi import APIRouter

from app.routers.v1.admin import exams, imports, questions, subjects, topics, users

router = APIRouter()
router.include_router(subjects.router)
router.include_router(topics.router)
router.include_router(exams.router)
router.include_router(questions.router)
router.include_router(imports.router)
router.include_router(users.router)
