from fastapi import APIRouter

from app.api.routes.book_index import router as book_index_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.scripts import router as scripts_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(projects_router)
api_router.include_router(book_index_router)
api_router.include_router(scripts_router)
