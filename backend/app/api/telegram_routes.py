from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import User
from app.api.deps import get_current_user
from app.services.telegram_bot import TelegramBot

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming Telegram updates."""
    data = await request.json()

    bot = TelegramBot(db)
    await bot.handle_update(data)

    return {"ok": True}


@router.post("/link")
async def link_telegram(
    telegram_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link Telegram account to user using a verification code."""
    bot = TelegramBot(db)
    chat_id = await bot.verify_code(telegram_code)

    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail="Codigo invalido ou expirado. Use /vincular no bot para gerar um novo.",
        )

    # Check if chat_id already linked to another user
    existing = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id, User.id != current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Este Telegram ja esta vinculado a outra conta",
        )

    current_user.telegram_chat_id = chat_id
    await db.commit()

    return {"message": "Telegram vinculado com sucesso"}


@router.delete("/unlink")
async def unlink_telegram(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlink Telegram account from user."""
    if not current_user.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail="Nenhum Telegram vinculado",
        )

    current_user.telegram_chat_id = None
    await db.commit()

    return {"message": "Telegram desvinculado com sucesso"}


@router.get("/status")
async def telegram_status(
    current_user: User = Depends(get_current_user),
):
    """Check if Telegram is linked."""
    return {
        "linked": current_user.telegram_chat_id is not None,
        "chat_id": current_user.telegram_chat_id,
    }
