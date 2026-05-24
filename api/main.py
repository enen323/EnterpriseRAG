from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db
from api.auth import router as auth_router
from api.documents import router as documents_router
from api.qa import router as qa_router
from api.conversations import router as conversations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health")
async def health():
    return {"status": "ok"}
