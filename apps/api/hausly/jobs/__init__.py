"""Background jobs scheduler.

Uses APScheduler to run recurring jobs:
- Recurring expense generation (daily at 02:00 UTC)
- Chore assignment generation (daily at 02:05 UTC)

Jobs also run once at startup to catch up on missed runs.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from hausly.database import async_session_factory, engine
from hausly.jobs.chore_assignments import process_chore_assignments
from hausly.jobs.recurring_expenses import process_recurring_expenses
from sqlalchemy import text

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_recurring_expenses() -> None:
    """Wrapper that provides a DB session for the recurring expenses job."""
    async with async_session_factory() as db:
        try:
            stats = await process_recurring_expenses(db)
            logger.info("Recurring expenses job completed: %s", stats)
        except OSError as e:
            if "Connect call failed" in str(e):
                logger.error(
                    "PostgreSQL is not reachable. "
                    "Start the database with: docker compose up -d"
                )
            else:
                logger.exception("Recurring expenses job failed")
        except Exception:
            logger.exception("Recurring expenses job failed")


async def _run_chore_assignments() -> None:
    """Wrapper that provides a DB session for the chore assignments job."""
    async with async_session_factory() as db:
        try:
            stats = await process_chore_assignments(db)
            logger.info("Chore assignments job completed: %s", stats)
        except OSError as e:
            if "Connect call failed" in str(e):
                logger.error(
                    "PostgreSQL is not reachable. "
                    "Start the database with: docker compose up -d"
                )
            else:
                logger.exception("Chore assignments job failed")
        except Exception:
            logger.exception("Chore assignments job failed")


def setup_scheduler() -> None:
    """Configure scheduled jobs. Call once during app startup."""
    scheduler.add_job(
        _run_recurring_expenses,
        trigger=CronTrigger(hour=2, minute=0),
        id="recurring_expenses",
        name="Generate recurring expense drafts",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_chore_assignments,
        trigger=CronTrigger(hour=2, minute=5),
        id="chore_assignments",
        name="Generate chore assignments (14-day window)",
        replace_existing=True,
    )


@asynccontextmanager
async def lifespan_jobs(app):
    """FastAPI lifespan context manager for background jobs."""
    # Verify database connectivity before starting jobs
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError:
        logger.error(
            "\n"
            "══════════════════════════════════════════════════════════\n"
            "  PostgreSQL is not reachable!\n"
            "  Start the database with:  docker compose up -d\n"
            "  (from apps/api/ directory)\n"
            "══════════════════════════════════════════════════════════"
        )
        yield
        return
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        yield
        return

    setup_scheduler()
    scheduler.start()
    logger.info("Background job scheduler started")

    # Run jobs once at startup to catch up
    await _run_recurring_expenses()
    await _run_chore_assignments()

    yield

    scheduler.shutdown(wait=False)
    logger.info("Background job scheduler stopped")
