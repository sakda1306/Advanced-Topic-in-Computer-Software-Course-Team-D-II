"""Login / logout / me and user preferences (CONTRACT §1)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import ContainerDep, CurrentUser, DbDep
from app.core.security import create_access_token
from app.infra.rate_limit import enforce_rate_limit
from app.schemas.common import Ok
from app.schemas.user import LoginRequest, PreferencesRequest, UserEnvelope, UserOut
from app.services.users import authenticate

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    container: ContainerDep,
    db: DbDep,
) -> UserEnvelope:
    settings = container.settings
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        container.store, "login", client_ip, settings.login_rate_limit_per_minute
    )
    user = await authenticate(db, body.username, body.password)
    response.set_cookie(
        settings.cookie_name,
        create_access_token(settings, user.id, user.role),
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return UserEnvelope(user=UserOut.of(user))


@router.post("/auth/logout")
async def logout(response: Response, container: ContainerDep) -> Ok:
    settings = container.settings
    response.delete_cookie(
        settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )
    return Ok()


@router.get("/auth/me")
async def me(user: CurrentUser) -> UserEnvelope:
    return UserEnvelope(user=UserOut.of(user))


@router.patch("/me/preferences")
async def update_preferences(
    body: PreferencesRequest, user: CurrentUser, db: DbDep
) -> UserEnvelope:
    sent = body.model_fields_set
    if "favorite_team_id" in sent:
        user.favorite_team_id = body.favorite_team_id
    if "language" in sent and body.language is not None:
        user.language = body.language
    await db.commit()
    return UserEnvelope(user=UserOut.of(user))
