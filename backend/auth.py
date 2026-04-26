"""
backend/auth.py — User authentication: register, login, JWT, password reset.
"""
import os
import bcrypt
import jwt
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

JWT_SECRET = os.environ.get("JWT_SECRET", "arknights-rag-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

# Password: 8-16 chars, ASCII printable except space/control
PASSWORD_PATTERN = re.compile(r'^[\x21-\x7E]{8,16}$')
# Account: 1-16 chars, alphanumeric + underscore
ACCOUNT_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,16}$')
# Username: 1-16 chars (any unicode)
USERNAME_PATTERN = re.compile(r'^.{1,16}$', re.DOTALL)


def validate_account(account: str) -> Optional[str]:
    if not ACCOUNT_PATTERN.match(account):
        return "账号只能包含英文、数字和下划线，长度1-16"
    return None


def validate_username(username: str) -> Optional[str]:
    if not USERNAME_PATTERN.match(username.strip()):
        return "用户名长度1-16个字符"
    return None


def validate_password(password: str) -> Optional[str]:
    if not PASSWORD_PATTERN.match(password):
        return "密码长度8-16个字符，支持大小写英文、数字和常见符号"
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_jwt(user_id: int, account: str, username: str, password_changed_at: str) -> str:
    payload = {
        'user_id': user_id,
        'account': account,
        'username': username,
        'pw_changed_at': password_changed_at,
        'exp': datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
