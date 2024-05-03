from enum import StrEnum
from secrets import token_urlsafe
from typing import Literal
from pydantic import BaseModel, Field


class MetaPermission(StrEnum):
    ADMIN = "meta.admin"
    CREATE = "meta.create"


class PackagePermission(StrEnum):
    MANAGE = "pkg.manage"
    EDIT = "pkg.edit"
    VIEW = "pkg.view"


class AuthUser(BaseModel):
    id: str
    type: Literal["user"] = "user"
    username: str | None = None
    password_hash: str | None = None
    password_salt: str | None = None
    groups: list[str] = []


class AuthGroup(BaseModel):
    id: str
    name: str
    display_name: str | None = None


class RedactedAuth(BaseModel):
    id: str | None
    type: Literal["user", "token", "admin", "anonymous"]
    name: str | None
    groups: list[AuthGroup]
    linked: AuthUser | None = None


class AuthAdmin(BaseModel):
    type: Literal["admin"] = "admin"
    username: str | None = None

    @property
    def id(self) -> str:
        return "_admin"


class AuthToken(BaseModel):
    id: str
    token: str | None = Field(default_factory=lambda: token_urlsafe())
    type: Literal["token"] = "token"
    linked_user: str | None = None
    description: str | None = None
    groups: list[str] = []


class AuthPermission(BaseModel):
    id: str
    permission: PackagePermission | MetaPermission
    target_type: Literal["group", "auth"]
    target_id: str
    project: str | None = None
