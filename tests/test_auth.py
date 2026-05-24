import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from core.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, poolclass=StaticPool)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/api/auth/register", json={"username": "dupuser", "password": "pass123"})
    resp = await client.post("/api/auth/register", json={"username": "dupuser", "password": "pass456"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={"username": "loginuser", "password": "mypass"})
    resp = await client.post("/api/auth/login", json={"username": "loginuser", "password": "mypass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={"username": "authuser", "password": "correct"})
    resp = await client.post("/api/auth/login", json={"username": "authuser", "password": "wrong"})
    assert resp.status_code == 401
