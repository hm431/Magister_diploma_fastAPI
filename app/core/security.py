
# create_refresh_token
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    '''
    Хешируем пароль для пользователя
    '''
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    '''
    Проверяем пароль пользователя при логине
    '''
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    '''
    Создаем JWT для сесии
    '''
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    '''
    Создаем JWT для обновления access токена
    '''
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    '''
    Декодируем и проверяем JWT токен
    '''
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
