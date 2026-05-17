from app.db.base_class import Base, TimestampMixin  # noqa: F401

# Импорты моделей — нужны, чтобы Base.metadata знал обо всех таблицах
# при вызове create_all в lifespan.
from app.models.user import User                              # noqa: F401
from app.models.ref_object import (                           # noqa: F401
    ObjectRef, Site, WorkType, Material, Warehouse, Supplier,
)
from app.models.ref_brigade import Brigade                    # noqa: F401
from app.models.norm import (                                 # noqa: F401
    BrigadeQualification, ConsumptionNorm, SupplyContract, TransportParam,
)
from app.models.mtr import (                                  # noqa: F401
    StockBalance, MaterialDemand,
    PlannedDelivery, MaterialAvailabilityDate, WarehouseLoadProfile,
)
from app.models.sro import (                                  # noqa: F401
    Project, Work, WorkPredecessor,
    ScheduleCalculation, ScheduleItem, BrigadeAssignment,
)
from app.models.risk import (                                 # noqa: F401
    WorkRiskParams, SupplierDeliveryStats,
    MonteCarloRun, MonteCarloIteration,
    RiskQuantile, WorkCriticalityIndex,
)
from app.models.mtr import (                                  # noqa: F401 (дополнение — фактические данные)
    ActualDelivery, StockMovement,
)
from app.models.ops import (                                  # noqa: F401
    WorkProgress, Deviation, DeviationCause, CorrectionScenario,
)
