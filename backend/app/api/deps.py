from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.models import User, Processo, ProcessoUser

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario nao encontrado",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desativado",
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user


async def get_processo_with_access(
    processo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Processo:
    """Get processo and verify user has access (owner or shared)."""
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo nao encontrado",
        )

    # Check if user is owner
    if processo.owner_id == current_user.id:
        return processo

    # Check if user has shared access
    shared_result = await db.execute(
        select(ProcessoUser).where(
            ProcessoUser.processo_id == processo_id,
            ProcessoUser.user_id == current_user.id,
        )
    )
    shared = shared_result.scalar_one_or_none()

    if not shared:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado a este processo",
        )

    return processo


async def get_processo_as_editor(
    processo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Processo:
    """Get processo and verify user can edit (owner or editor role)."""
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo nao encontrado",
        )

    # Owner can always edit
    if processo.owner_id == current_user.id:
        return processo

    # Check if user has editor access
    shared_result = await db.execute(
        select(ProcessoUser).where(
            ProcessoUser.processo_id == processo_id,
            ProcessoUser.user_id == current_user.id,
            ProcessoUser.role == "editor",
        )
    )
    shared = shared_result.scalar_one_or_none()

    if not shared:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissao de edicao negada",
        )

    return processo
