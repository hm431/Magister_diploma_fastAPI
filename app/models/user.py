from typing import Optional
from datetime import datetime
from sqlalchemy import String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class User(Base):
    '''public.user - таблица пользователей'''
    __tablename__ = "user"
    __table_args__ = {"schema": "public"}   
    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    role:  Mapped[str] = mapped_column(nullable=False, default="viewer") 	
    is_active: Mapped[bool] = mapped_column(nullable=False, default="True") 	
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
