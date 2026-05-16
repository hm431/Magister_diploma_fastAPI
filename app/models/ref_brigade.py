from __future__ import annotations
from typing import Optional, List

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Brigade(Base):
    """ref.brigade — производственные бригады."""
    __tablename__ = "brigade"
    __table_args__ = {"schema": "ref"}

    brigade_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    base_location: Mapped[Optional[str]] = mapped_column(String(255))

    qualifications: Mapped[List["BrigadeQualification"]] = relationship(
        "BrigadeQualification", back_populates="brigade"
    )
