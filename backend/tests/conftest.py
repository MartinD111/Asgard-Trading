"""
Shared pytest fixtures. DB/Redis not required for pure-function unit tests.
Integration fixtures (async client, DB session) will be added in M3.
"""
import os
import sys
import types
import pytest

# Provide minimal env so modules that read secrets at import time don't blow up.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")

# Stub out native packages that aren't installed in the local Python 3.14 dev
# environment but ARE present in the Docker runtime. Tests never exercise real
# DB/auth paths, so these stubs only need to satisfy import-time references.
from unittest.mock import MagicMock

if "asyncpg" not in sys.modules:
    _asyncpg = MagicMock()
    _asyncpg.exceptions.PostgresError = Exception
    _asyncpg.exceptions.InterfaceError = Exception
    sys.modules["asyncpg"] = _asyncpg
    sys.modules["asyncpg.exceptions"] = _asyncpg.exceptions

if "passlib" not in sys.modules:
    _passlib = MagicMock()
    # CryptContext is instantiated at auth_service import time; the MagicMock
    # instance it returns is stored as pwd_context and never called in tests.
    sys.modules["passlib"] = _passlib
    sys.modules["passlib.context"] = _passlib.context
    sys.modules["passlib.handlers"] = _passlib.handlers
    sys.modules["passlib.handlers.bcrypt"] = MagicMock()

if "bcrypt" not in sys.modules:
    sys.modules["bcrypt"] = MagicMock()

if "jose" not in sys.modules:
    _jose = MagicMock()
    # JWTError must be a real exception class so `except JWTError` clauses work
    _jose.JWTError = type("JWTError", (Exception,), {})
    sys.modules["jose"] = _jose
    sys.modules["jose.jwt"] = _jose.jwt
    sys.modules["jose.exceptions"] = _jose.exceptions

if "google" not in sys.modules or "google.generativeai" not in sys.modules:
    _google = MagicMock()
    sys.modules["google"] = _google
    sys.modules["google.generativeai"] = _google.generativeai

if "chromadb" not in sys.modules:
    _chroma = MagicMock()
    sys.modules["chromadb"] = _chroma
    sys.modules["chromadb.utils"] = _chroma.utils
    sys.modules["chromadb.utils.embedding_functions"] = _chroma.utils.embedding_functions
