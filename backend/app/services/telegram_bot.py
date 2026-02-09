import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.models import User, Processo, Conversation, Message
from app.services.rag_engine import chat as rag_chat

settings = get_settings()

# In-memory store for verification codes (in production, use Redis)
verification_codes: dict[str, tuple[int, datetime]] = {}


class TelegramBot:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.token = settings.TELEGRAM_BOT_TOKEN

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Send a message to a Telegram chat."""
        import aiohttp

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })

    async def handle_update(self, update: dict):
        """Handle incoming Telegram update."""
        if "message" not in update:
            return

        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # Get user by telegram_chat_id
        result = await self.db.execute(
            select(User).where(User.telegram_chat_id == chat_id)
        )
        user = result.scalar_one_or_none()

        # Handle commands
        if text.startswith("/start"):
            await self._handle_start(chat_id, user)
        elif text.startswith("/vincular"):
            await self._handle_vincular(chat_id)
        elif text.startswith("/processos"):
            await self._handle_processos(chat_id, user)
        elif text.startswith("/selecionar"):
            await self._handle_selecionar(chat_id, user, text)
        elif text.startswith("/ajuda") or text.startswith("/help"):
            await self._handle_help(chat_id)
        elif user:
            # Regular message - send to RAG
            await self._handle_message(chat_id, user, text)
        else:
            await self.send_message(
                chat_id,
                "Voce precisa vincular sua conta primeiro.\n"
                "Use /vincular para gerar um codigo de vinculacao."
            )

    async def _handle_start(self, chat_id: int, user: Optional[User]):
        """Handle /start command."""
        if user:
            await self.send_message(
                chat_id,
                f"Ola {user.name}! Bem-vindo ao Apoio Processual.\n\n"
                "Use /processos para ver seus processos.\n"
                "Use /selecionar [numero] para selecionar um processo.\n"
                "Use /ajuda para ver todos os comandos."
            )
        else:
            await self.send_message(
                chat_id,
                "Bem-vindo ao Apoio Processual!\n\n"
                "Para comecar, voce precisa vincular sua conta.\n"
                "Use /vincular para gerar um codigo de vinculacao."
            )

    async def _handle_vincular(self, chat_id: int):
        """Handle /vincular command - generate verification code."""
        code = secrets.token_hex(4).upper()  # 8 character code
        verification_codes[code] = (chat_id, datetime.utcnow() + timedelta(minutes=10))

        await self.send_message(
            chat_id,
            f"Seu codigo de vinculacao e: <code>{code}</code>\n\n"
            "Use este codigo no painel web para vincular sua conta.\n"
            "O codigo expira em 10 minutos."
        )

    async def verify_code(self, code: str) -> Optional[int]:
        """Verify a code and return the chat_id if valid."""
        code = code.upper()
        if code not in verification_codes:
            return None

        chat_id, expires_at = verification_codes[code]
        if datetime.utcnow() > expires_at:
            del verification_codes[code]
            return None

        del verification_codes[code]
        return chat_id

    async def _handle_processos(self, chat_id: int, user: Optional[User]):
        """Handle /processos command - list user's processes."""
        if not user:
            await self.send_message(chat_id, "Voce precisa vincular sua conta primeiro.")
            return

        result = await self.db.execute(
            select(Processo)
            .where(Processo.owner_id == user.id, Processo.status == "ativo")
            .order_by(Processo.updated_at.desc())
            .limit(10)
        )
        processos = result.scalars().all()

        if not processos:
            await self.send_message(chat_id, "Voce nao tem processos ativos.")
            return

        text = "Seus processos:\n\n"
        for i, p in enumerate(processos, 1):
            text += f"{i}. <b>{p.titulo}</b>"
            if p.numero:
                text += f" ({p.numero})"
            text += "\n"

        text += "\nUse /selecionar [numero] para selecionar um processo."
        await self.send_message(chat_id, text)

    async def _handle_selecionar(self, chat_id: int, user: Optional[User], text: str):
        """Handle /selecionar command - select a process for chat."""
        if not user:
            await self.send_message(chat_id, "Voce precisa vincular sua conta primeiro.")
            return

        # Parse process number
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(
                chat_id,
                "Use: /selecionar [numero]\nExemplo: /selecionar 1"
            )
            return

        try:
            idx = int(parts[1]) - 1
        except ValueError:
            await self.send_message(chat_id, "Numero invalido.")
            return

        # Get processos
        result = await self.db.execute(
            select(Processo)
            .where(Processo.owner_id == user.id, Processo.status == "ativo")
            .order_by(Processo.updated_at.desc())
            .limit(10)
        )
        processos = list(result.scalars().all())

        if idx < 0 or idx >= len(processos):
            await self.send_message(chat_id, "Numero de processo invalido.")
            return

        processo = processos[idx]

        # Create or get conversation for this processo
        conv_result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.processo_id == processo.id,
                Conversation.user_id == user.id,
                Conversation.canal == "telegram",
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                processo_id=processo.id,
                user_id=user.id,
                canal="telegram",
                titulo=f"Telegram - {processo.titulo}",
            )
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)

        # Store active processo in user metadata (simple approach)
        # In production, use a separate table or Redis
        await self.send_message(
            chat_id,
            f"Processo selecionado: <b>{processo.titulo}</b>\n\n"
            "Agora voce pode enviar perguntas sobre este processo."
        )

    async def _handle_message(self, chat_id: int, user: User, text: str):
        """Handle regular message - send to RAG."""
        # Get user's most recent telegram conversation
        conv_result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.canal == "telegram",
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            await self.send_message(
                chat_id,
                "Selecione um processo primeiro.\n"
                "Use /processos para ver seus processos."
            )
            return

        # Get conversation history
        history_result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .limit(20)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in history_result.scalars().all()
        ]

        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=text,
        )
        self.db.add(user_message)
        await self.db.commit()

        # Send "typing" indicator
        await self._send_typing(chat_id)

        # Get RAG response
        try:
            rag_result = await rag_chat(
                query=text,
                conversation_history=history,
                db=self.db,
                processo_id=conversation.processo_id,
            )

            # Save assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=rag_result["answer"],
                chunks_usados=[UUID(c) for c in rag_result["chunks_used"]],
                tokens_input=rag_result["tokens_input"],
                tokens_output=rag_result["tokens_output"],
                custo_estimado=rag_result["cost_usd"],
            )
            self.db.add(assistant_message)
            await self.db.commit()

            # Send response
            await self.send_message(chat_id, rag_result["answer"])

        except Exception as e:
            await self.send_message(
                chat_id,
                "Desculpe, ocorreu um erro ao processar sua mensagem. "
                "Tente novamente mais tarde."
            )

    async def _send_typing(self, chat_id: int):
        """Send typing indicator."""
        import aiohttp

        url = f"https://api.telegram.org/bot{self.token}/sendChatAction"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": chat_id,
                "action": "typing",
            })

    async def _handle_help(self, chat_id: int):
        """Handle /ajuda command."""
        await self.send_message(
            chat_id,
            "<b>Comandos disponiveis:</b>\n\n"
            "/start - Iniciar o bot\n"
            "/vincular - Gerar codigo para vincular conta\n"
            "/processos - Listar seus processos\n"
            "/selecionar [n] - Selecionar processo por numero\n"
            "/ajuda - Mostrar esta ajuda\n\n"
            "Apos selecionar um processo, basta enviar sua pergunta!"
        )
