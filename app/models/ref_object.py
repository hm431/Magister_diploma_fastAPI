from typing import Optional

from sqlalchemy import String, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class ObjectRef(Base):
    """ref.object — объекты строительства."""
    __tablename__ = "object"
    __table_args__ = {"schema": "ref"}

    object_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_start: Mapped[Optional[Date]] = mapped_column(Date)
    planned_finish: Mapped[Optional[Date]] = mapped_column(Date)

    sites = relationship("Site", back_populates="object")
    projects = relationship("Project", back_populates="object")


class Site(Base):
    """ref.site — строительные участки."""
    __tablename__ = "site"
    __table_args__ = {"schema": "ref"}

    site_id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("ref.object.object_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_x: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))  # координата X (г_ks)
    location_y: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))  # координата Y (г_ks)

    object = relationship("ObjectRef", back_populates="sites")


class WorkType(Base):
    """ref.work_type — типы СМР."""
    __tablename__ = "work_type"
    __table_args__ = {"schema": "ref"}

    work_type_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)


class Material(Base):
    """ref.material — номенклатурный справочник материалов."""
    __tablename__ = "material"
    __table_args__ = {"schema": "ref"}

    material_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_coefficient: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))  # w_j (2.22)
    safety_stock: Mapped[Optional[float]] = mapped_column(Numeric(12, 3))        # Z_j^мин (2.15)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    requires_certification: Mapped[bool] = mapped_column(default=False)


class Warehouse(Base):
    """ref.warehouse — склады отгрузки и приёмки."""
    __tablename__ = "warehouse"
    __table_args__ = {"schema": "ref"}

    warehouse_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    capacity: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))      # U_max (2.23)
    loading_posts: Mapped[int] = mapped_column(default=1)                  # n_р (2.26)
    service_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))   # μ (2.26)
    allowed_wait_time: Mapped[Optional[int]] = mapped_column()             # W_q^доп (2.30)


class Supplier(Base):
    """ref.supplier — справочник поставщиков."""
    __tablename__ = "supplier"
    __table_args__ = {"schema": "ref"}

    supplier_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12))
    reliability_class: Mapped[Optional[str]] = mapped_column(String(1))