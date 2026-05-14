"""
core/exceptions.py

Доменные исключения системы и обработчики, превращающие их в HTTP-ответы.
Регистрация хендлеров вызывается из main.py:  register_exception_handlers(app)
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger


# ============================================================
#  Базовый класс — от него наследуются все доменные исключения
# ============================================================
class AppException(Exception):
    """Базовое исключение приложения."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "Внутренняя ошибка сервера"

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


# ============================================================
#  Исключения «ресурс не найден» (HTTP 404)
# ============================================================
class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Объект не найден"


class ProjectNotFoundError(NotFoundError):
    error_code = "PROJECT_NOT_FOUND"

    def __init__(self, project_id: int):
        super().__init__(
            message=f"Проект с id={project_id} не найден",
            details={"project_id": project_id},
        )


class WorkNotFoundError(NotFoundError):
    error_code = "WORK_NOT_FOUND"

    def __init__(self, work_id: int):
        super().__init__(
            message=f"Работа с id={work_id} не найдена",
            details={"work_id": work_id},
        )


class MaterialNotFoundError(NotFoundError):
    error_code = "MATERIAL_NOT_FOUND"

    def __init__(self, material_id: int):
        super().__init__(
            message=f"Материал с id={material_id} не найден",
            details={"material_id": material_id},
        )


# ============================================================
#  Авторизация и доступ (HTTP 401 / 403)
# ============================================================
class AuthenticationError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    message = "Не удалось пройти аутентификацию"


class InvalidCredentialsError(AuthenticationError):
    error_code = "INVALID_CREDENTIALS"
    message = "Неверный логин или пароль"


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"
    message = "Срок действия токена истёк"


class PermissionDeniedError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "PERMISSION_DENIED"
    message = "Недостаточно прав для выполнения операции"


# ============================================================
#  Доменные ошибки бизнес-логики (HTTP 400 / 422)
# ============================================================
class ValidationError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    message = "Ошибка валидации данных"


class CyclicDependencyError(ValidationError):
    """Циклическая зависимость в предшественниках работ (раздел 3.3.4)."""
    error_code = "CYCLIC_DEPENDENCY"
    message = "Обнаружен цикл в технологической последовательности работ"


class BusinessRuleViolationError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "BUSINESS_RULE_VIOLATION"
    message = "Нарушено бизнес-правило"


class ScheduleCalculationError(AppException):
    """Ошибка расчёта календарного графика (CPM/RCPSP)."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "SCHEDULE_CALCULATION_FAILED"
    message = "Не удалось рассчитать календарный график"


class WarehouseCapacityExceededError(BusinessRuleViolationError):
    """Превышение паспортной вместимости склада U_max (2.19–2.22)."""
    error_code = "WAREHOUSE_CAPACITY_EXCEEDED"
    message = "Превышена паспортная вместимость склада"


# ============================================================
#  Интеграция с 1С
# ============================================================
class ExternalServiceError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "Ошибка взаимодействия с внешней системой"


class OneCIntegrationError(ExternalServiceError):
    error_code = "ONE_C_INTEGRATION_ERROR"
    message = "Ошибка взаимодействия с 1С:Предприятие"


# ============================================================
#  Регистрация обработчиков в FastAPI
# ============================================================
def _error_response(exc: AppException) -> JSONResponse:
    """Единый формат ответа об ошибке для фронтенда."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует все обработчики исключений. Вызывается из main.py."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            f"AppException: {exc.error_code} | {exc.message} | "
            f"path={request.url.path} | details={exc.details}"
        )
        return _error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Ошибки валидации Pydantic — приводим к нашему формату."""
        logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "Ошибка валидации входных данных",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """Ошибки БД — не показываем пользователю внутренние детали."""
        logger.error(f"DB error on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Ошибка при обращении к базе данных",
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Последний рубеж — всё, что не поймали выше."""
        logger.exception(f"Unhandled exception on {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Внутренняя ошибка сервера",
                    "details": {},
                }
            },
        )