from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.database import Base, engine
from config.settings import settings
from models import db_models  # pyright: ignore[reportUnusedImport]
from routes.auth_routes import router as auth_router
from routes.item_routes import router as item_router
from routes.post_routes import router as post_router
from routes.users_routes import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Create database tables on application startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(item_router)
app.include_router(user_router)
app.include_router(post_router)


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"message": f"Welcome to {settings.APP_NAME}"}
