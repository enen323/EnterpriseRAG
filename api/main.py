from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db
from api.auth import router as auth_router
from api.documents import router as documents_router
from api.qa import router as qa_router
from api.conversations import router as conversations_router
from api.admin import router as admin_router
from api.categories import router as categories_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # New tables (MessageFeedback, Category etc.) are auto-created by init_db() via SQLAlchemy create_all
    await init_db()
    yield


app = FastAPI(title="EnterpriseRAG API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(qa_router)
app.include_router(conversations_router)
app.include_router(admin_router)
app.include_router(categories_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
