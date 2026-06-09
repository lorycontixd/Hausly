"""Recurring expense generation job.

Runs daily. For each recurring expense where next_occurrence_date <= today:
- Skips if 3+ unconfirmed drafts exist (staleness cap)
- Creates a draft expense with the same splits
- Advances next_occurrence_date per recurrence_rule
"""

import logging
import uuid
from datetime import date

from dateutil.relativedelta import relativedelta
from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

logger = logging.getLogger(__name__)

STALENESS_CAP = 3


def _parse_rrule(rule: str) -> tuple[int, str]:
    """Parse a simple recurrence rule string like 'FREQ=MONTHLY;INTERVAL=1'.

    Returns (interval, unit) where unit is one of: daily, weekly, monthly.
    """
    parts = {k: v for k, v in (p.split("=") for p in rule.split(";"))}
    freq = parts.get("FREQ", "MONTHLY").upper()
    interval = int(parts.get("INTERVAL", "1"))

    unit_map = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}
    unit = unit_map.get(freq, "monthly")
    return interval, unit


def _advance_occurrence_date(current: date, rule: str) -> date:
    """Advance a date by the recurrence rule."""
    interval, unit = _parse_rrule(rule)

    if unit == "daily":
        return current + relativedelta(days=interval)
    elif unit == "weekly":
        return current + relativedelta(weeks=interval)
    elif unit == "monthly":
        return current + relativedelta(months=interval)
    return current + relativedelta(months=interval)


async def _count_unconfirmed_drafts(
    db: AsyncSession,
    household_id: uuid.UUID,
    title: str,
) -> int:
    """Count unconfirmed drafts for a recurring expense (matched by title + source)."""
    stmt = select(func.count()).select_from(Expense).where(
        Expense.household_id == household_id,
        Expense.title == title,
        Expense.source == ExpenseSource.recurring_auto,
        Expense.status == ExpenseStatus.draft,
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def _get_splits_for_expense(
    db: AsyncSession, expense_id: uuid.UUID
) -> list[ExpenseSplit]:
    """Load splits for a template expense."""
    stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def process_recurring_expenses(db: AsyncSession) -> dict[str, int]:
    """Process all due recurring expenses. Returns stats."""
    today = date.today()
    stats = {"processed": 0, "generated": 0, "skipped_stale": 0}

    stmt = select(Expense).where(
        Expense.is_recurring == True,  # noqa: E712
        Expense.next_occurrence_date <= today,
        Expense.status == ExpenseStatus.confirmed,
    )
    result = await db.execute(stmt)
    recurring_expenses = list(result.scalars().all())

    for template in recurring_expenses:
        stats["processed"] += 1

        if not template.recurrence_rule:
            logger.warning(
                "Recurring expense %s has no recurrence_rule, skipping", template.id
            )
            continue

        # Check staleness cap
        unconfirmed_count = await _count_unconfirmed_drafts(
            db, template.household_id, template.title
        )
        if unconfirmed_count >= STALENESS_CAP:
            stats["skipped_stale"] += 1
            logger.info(
                "Recurring expense %s has %d unconfirmed drafts (cap=%d), skipping",
                template.id,
                unconfirmed_count,
                STALENESS_CAP,
            )
            continue

        # Load template splits
        template_splits = await _get_splits_for_expense(db, template.id)

        # Create draft expense
        draft = Expense(
            household_id=template.household_id,
            title=template.title,
            amount=template.amount,
            currency=template.currency,
            category=template.category,
            paid_by_user_id=template.paid_by_user_id,
            is_recurring=False,
            status=ExpenseStatus.draft,
            source=ExpenseSource.recurring_auto,
        )
        db.add(draft)
        await db.flush()

        # Create splits for the draft
        for split in template_splits:
            new_split = ExpenseSplit(
                expense_id=draft.id,
                household_id=template.household_id,
                user_id=split.user_id,
                share_amount=split.share_amount,
            )
            db.add(new_split)

        # Advance next_occurrence_date on the template
        template.next_occurrence_date = _advance_occurrence_date(
            template.next_occurrence_date, template.recurrence_rule
        )

        stats["generated"] += 1
        logger.info(
            "Generated draft expense from recurring %s, next occurrence: %s",
            template.id,
            template.next_occurrence_date,
        )

    await db.commit()
    return stats
