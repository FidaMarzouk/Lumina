"""Accounts: sign-up, log-in/out, settings, export and deletion.

Errors are deliberately generic ("email or password is incorrect"), failed logins are rate-limited
per email + client address, and a login takes the same time whether or not the email exists.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from ..auth import passwords, tokens
from ..auth.deps import bearer_token, current_user, get_store
from ..config import PASSWORD_MIN_CHARS
from ..memory.store import EmailTaken, Store

log = logging.getLogger(__name__)
router = APIRouter()
limiter = tokens.LoginLimiter()

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NAME_PUNCT = set(" '-.")


def _email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL.match(v):
        raise ValueError("Please enter a valid email address.")
    return v


def _name(v: str) -> str:
    # The name is placed in the LLM prompt, so only letters and a little punctuation are accepted.
    v = " ".join(v.split())
    if not all(ch.isalpha() or ch in _NAME_PUNCT for ch in v):
        raise ValueError("Please use letters only in your name.")
    return v


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=PASSWORD_MIN_CHARS, max_length=128)
    display_name: str = Field(default="", max_length=40)
    consent: bool = False          # agrees to Lumina remembering derived notes (memory on)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _email(v)

    @field_validator("display_name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _name(v)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class SettingsRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=40)
    memory_enabled: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return v if v is None else _name(v)


class DeleteRequest(BaseModel):
    password: str = Field(max_length=128)


def public_user(user: dict) -> dict:
    return {k: user[k] for k in ("id", "email", "display_name", "created_at", "consent_at")} | {
        "memory_enabled": bool(user["memory_enabled"])}


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest, store: Store = Depends(get_store)):
    try:
        user = store.create_user(body.email, passwords.hash_password(body.password), body.display_name, body.consent)
    except EmailTaken:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Try logging in.")
    log.info("Account created — memory=%s", bool(user["memory_enabled"]))
    return {"token": tokens.issue(store, user["id"]), "user": public_user(user)}


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, store: Store = Depends(get_store)):
    email = body.email.strip().lower()
    key = f"{email}|{_client(request)}"
    if limiter.blocked(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a minute and try again.")
    user = store.get_user_by_email(email)
    ok = passwords.verify_password(body.password, user["password_hash"] if user else passwords.DUMMY_HASH)
    if not (user and ok):
        limiter.failed(key)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    limiter.reset(key)
    return {"token": tokens.issue(store, user["id"]), "user": public_user(user)}


@router.post("/auth/logout", status_code=204)
def logout(token: str | None = Depends(bearer_token), store: Store = Depends(get_store)):
    if token:
        tokens.revoke(store, token)
    return Response(status_code=204)


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.patch("/users/me")
def update_settings(body: SettingsRequest, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    updated = store.update_user(user["id"], display_name=body.display_name, memory_enabled=body.memory_enabled)
    return public_user(updated)


@router.get("/users/me/export")
def export(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return store.export_user(user["id"])


@router.delete("/users/me", status_code=204)
def delete_account(body: DeleteRequest, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    if not passwords.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Password is incorrect.")
    store.delete_user(user["id"])
    log.info("Account deleted")
    return Response(status_code=204)
