from __future__ import annotations
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class BrigadeQualification(Base):
    """norm.brigade_qualification — квалификации бригад (многие-ко-многим)."""
    __tablename__ = "brigade_qualification"
    __table_args__ = {"schema": "norm"}

    brigade_id: Mapped[int] = mapped_column(
        ForeignKey("ref.brigade.brigade_id"), primary_key=True
    )
    qualification_id: Mapped[int] = mapped_column(
        ForeignKey("ref.qualification.qualification_id"), primary_key=True
    )

    brigade: Mapped["Brigade"] = relationship(  # noqa: F821
        "Brigade", back_populates="qualifications"
    )


class ConsumptionNorm(Base):
    """norm.consumption_norm — нормы расхода материалов r_{ij} (формула 2.9)."""
    __tablename__ = "consumption_norm"
    __table_args__ = {"schema": "norm"}

    work_type_id: Mapped[int] = mapped_column(
        ForeignKey("ref.work_type.work_type_id"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("ref.material.material_id"), primary_key=True
    )
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True)
    norm_value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
