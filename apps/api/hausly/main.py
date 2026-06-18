import logging

from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hausly.auth.router import router as auth_router
from hausly.config import settings
from hausly.jobs import lifespan_jobs
from hausly.middleware import RequestSizeLimitMiddleware
from hausly.modules.chores.router import router as chores_router
from hausly.modules.expense.router import router as expense_router
from hausly.modules.grocery.router import router as grocery_router
from hausly.modules.household.router import invite_router
from hausly.modules.household.router import router as household_router
from hausly.modules.meal.router import router as meal_router
from hausly.ratelimit import limiter, rate_limit_exceeded_handler
from hausly.realtime.router import router as realtime_router
from hausly.telemetry import ExceptionTraceMiddleware
from hausly.version import __version__
from slowapi.errors import RateLimitExceeded

# Initialize Application Insights (no-op if connection string is empty)
if settings.appinsights_connection_string:
    configure_azure_monitor(
        connection_string=settings.appinsights_connection_string,
        logger_name="hausly",
    )
logger = logging.getLogger("hausly")

app = FastAPI(
    title="Hausly API",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan_jobs,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ExceptionTraceMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

app.include_router(auth_router)
app.include_router(household_router)
app.include_router(invite_router)
app.include_router(grocery_router)
app.include_router(expense_router)
app.include_router(meal_router)
app.include_router(chores_router)
app.include_router(realtime_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
