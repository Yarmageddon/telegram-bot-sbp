from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, String, Text, Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now() -> datetime:
    """Время в UTC с таймзоной. Единая точка правды."""
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# РАСТЕНИЯ
# ═══════════════════════════════════════════════════════════════

class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    species = Column(String(120), nullable=True)

    # Через сколько дней поливать
    watering_days = Column(Integer, nullable=False, default=3)

    # Последний полив
    last_watered = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_plants_user_name", "user_id", "name"),
    )

    def next_watering(self) -> datetime:
        """Когда полить в следующий раз."""
        base = self.last_watered or self.created_at
        from datetime import timedelta
        return base + timedelta(days=self.watering_days)


# ═══════════════════════════════════════════════════════════════
# НАПОМИНАНИЯ (универсальные — для всех агентов)
# ═══════════════════════════════════════════════════════════════

class Reminder(Base):
    """
    Универсальное напоминание.

    related_type + related_id позволяют связать его с конкретным объектом
    (например, "plant" + plant.id), чтобы при обновлении объекта отменить
    или пересоздать напоминание.
    """
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)

    text = Column(Text, nullable=False)
    when = Column(DateTime(timezone=True), nullable=False, index=True)
    repeat = Column(String(20), nullable=True)  # daily / weekly / monthly / None
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending / sent / cancelled

    related_type = Column(String(40), nullable=True)  # "plant", "task"...
    related_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_reminders_status_when", "status", "when"),
        Index("ix_reminders_related", "related_type", "related_id"),
    )
