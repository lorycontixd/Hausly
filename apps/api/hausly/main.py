from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hausly.auth.router import router as auth_router
from hausly.config import settings

app = FastAPI(
    title="Hausly API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
