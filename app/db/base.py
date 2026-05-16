from app.db.base_class import Base, TimestampMixin  # noqa: F401

# Импорты моделей — нужны, чтобы Base.metadata знал обо всех таблицах
# при вызове create_all в lifespan.
from app.models.user import User                              # noqa: F401
from app.models.ref_object import ObjectRef, Site, WorkType  # noqa: F401
from app.models.ref_brigade import Brigade                    # noqa: F401
from app.models.norm import BrigadeQualification, ConsumptionNorm  # noqa: F401
from app.models.mtr import StockBalance, MaterialDemand       # noqa: F401
from app.models.sro import (                                  # noqa: F401
    Project, Work, WorkPredecessor,
    ScheduleCalculation, ScheduleItem, BrigadeAssignment,
)
