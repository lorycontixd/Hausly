"""Chore assignment generation job.

Runs daily. For each active recurring chore:
- Skips if has unresolved overdue assignment (overdue blocking)
- Generates assignments up to 14 days ahead (idempotent)
"""

import logging

from hausly.modules.chores.models import Chore, ChoreAssignee
from hausly.modules.chores.service import generate_assignments
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

logger = logging.getLogger(__name__)


async def _load_assignees(db: AsyncSession, chore_id) -> list[ChoreAssignee]:
    """Load assignees for a chore, ordered by position."""
    stmt = (
        select(ChoreAssignee)
        .where(ChoreAssignee.chore_id == chore_id)
        .order_by(ChoreAssignee.position)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def process_chore_assignments(db: AsyncSession) -> dict[str, int]:
    """Generate assignments for all active recurring chores. Returns stats."""
    stats = {"processed": 0, "generated": 0, "skipped_overdue": 0}

    stmt = select(Chore).where(
        Chore.is_active == True,  # noqa: E712
        Chore.is_recurring == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    chores = list(result.scalars().all())

    for chore in chores:
        stats["processed"] += 1

        assignees = await _load_assignees(db, chore.id)
        if not assignees:
            logger.warning("Chore %s has no assignees, skipping", chore.id)
            continue

        created = await generate_assignments(db, chore, assignees)
        if created:
            stats["generated"] += len(created)
            logger.info(
                "Generated %d assignments for chore %s (%s)",
                len(created),
                chore.id,
                chore.name,
            )
        else:
            # generate_assignments returns [] if overdue-blocked or nothing to generate
            stats["skipped_overdue"] += 1

    await db.commit()
    return stats
