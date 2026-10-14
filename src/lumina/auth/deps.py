"""FastAPI dependencies: the store, and the signed-in user from `Authorization: Bearer <token>`."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..memory.store import Store, default_store
from . import tokens

_bearer = HTTPBearer(auto_error=False)


def get_store() -> Store:
    return default_store()


def bearer_token(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str | None:
    return creds.credentials if creds is not None else None


def optional_user(token: str | None = Depends(bearer_token), store: Store = Depends(get_store)) -> dict | None:
    return tokens.resolve(store, token) if token else None


def current_user(user: dict | None = Depends(optional_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in again.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user
