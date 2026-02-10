"""Seed script: cria usuarios iniciais."""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password
from app.models.models import User


async def seed():
    async with AsyncSessionLocal() as session:
        # Verifica se o usuario ja existe
        result = await session.execute(
            select(User).where(User.email == "gabriel@admin.com")
        )
        if result.scalar_one_or_none():
            print("Seed: usuario gabriel@admin.com ja existe, pulando.")
            return

        admin = User(
            name="Gabriel",
            email="gabriel@admin.com",
            password_hash=hash_password("trocar123"),
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print("Seed: usuario gabriel@admin.com criado com sucesso.")


if __name__ == "__main__":
    asyncio.run(seed())
