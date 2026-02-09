import re
from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Optional, List

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import Transacao, Chunk

settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CATEGORIES = [
    "educacao",
    "saude",
    "moradia",
    "alimentacao",
    "transporte",
    "lazer",
    "vestuario",
    "servicos",
    "impostos",
    "outros",
]

EXTRACTION_PROMPT = """Analise o seguinte texto de extrato bancario e extraia as transacoes financeiras.

Para cada transacao, forneca:
- descricao: descricao da transacao
- valor: valor em reais (positivo para creditos, negativo para debitos)
- data: data no formato YYYY-MM-DD (se disponivel)
- categoria: uma das categorias: educacao, saude, moradia, alimentacao, transporte, lazer, vestuario, servicos, impostos, outros
- pagador: quem pagou (nome ou "incerto" se nao souber)
- beneficiario: quem recebeu (nome ou "incerto" se nao souber)
- confianca: nivel de confianca na classificacao de 0.0 a 1.0

Retorne um JSON com a lista de transacoes no formato:
{
    "transacoes": [
        {
            "descricao": "...",
            "valor": 0.00,
            "data": "YYYY-MM-DD",
            "categoria": "...",
            "pagador": "...",
            "beneficiario": "...",
            "confianca": 0.0
        }
    ]
}

Texto do extrato:
"""


class FinancialAnalyzer:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_transactions_from_chunk(
        self,
        chunk: Chunk,
        processo_id: UUID,
    ) -> List[Transacao]:
        """Extract financial transactions from a text chunk using LLM."""
        prompt = EXTRACTION_PROMPT + chunk.conteudo

        try:
            response = await openai_client.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "Voce e um assistente especializado em extrair transacoes financeiras de extratos bancarios."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            import json
            result = json.loads(response.choices[0].message.content)

            transacoes = []
            for t in result.get("transacoes", []):
                transacao = Transacao(
                    processo_id=processo_id,
                    descricao=t.get("descricao", ""),
                    valor=Decimal(str(t.get("valor", 0))) if t.get("valor") else None,
                    data=self._parse_date(t.get("data")),
                    pagador=t.get("pagador"),
                    beneficiario=t.get("beneficiario"),
                    categoria=t.get("categoria") if t.get("categoria") in CATEGORIES else "outros",
                    confianca=float(t.get("confianca", 0.5)),
                    chunks_fonte=[chunk.id],
                    documento_ids=[chunk.documento_id],
                    trecho_evidencia=chunk.conteudo[:500],
                )
                transacoes.append(transacao)

            return transacoes

        except Exception as e:
            # Log error but don't fail
            print(f"Error extracting transactions: {e}")
            return []

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None

        try:
            # Try YYYY-MM-DD format
            return date.fromisoformat(date_str)
        except ValueError:
            pass

        # Try DD/MM/YYYY format
        match = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
        if match:
            day, month, year = match.groups()
            return date(int(year), int(month), int(day))

        return None

    async def analyze_document(
        self,
        documento_id: UUID,
        processo_id: UUID,
    ) -> List[Transacao]:
        """Analyze all chunks of a document for financial transactions."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(Chunk).where(Chunk.documento_id == documento_id)
        )
        chunks = result.scalars().all()

        all_transacoes = []
        for chunk in chunks:
            transacoes = await self.extract_transactions_from_chunk(chunk, processo_id)
            all_transacoes.extend(transacoes)

        # Save to database
        for t in all_transacoes:
            self.db.add(t)

        await self.db.commit()

        return all_transacoes

    async def categorize_transaction(
        self,
        transacao: Transacao,
    ) -> Transacao:
        """Re-categorize a transaction using LLM."""
        prompt = f"""Categorize a seguinte transacao bancaria:

Descricao: {transacao.descricao}
Valor: R$ {transacao.valor}
Data: {transacao.data}

Categorias disponiveis: {', '.join(CATEGORIES)}

Responda com um JSON no formato:
{{
    "categoria": "categoria_escolhida",
    "pagador": "quem_pagou_ou_incerto",
    "confianca": 0.0
}}"""

        try:
            response = await openai_client.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            import json
            result = json.loads(response.choices[0].message.content)

            transacao.categoria = result.get("categoria", transacao.categoria)
            transacao.pagador = result.get("pagador", transacao.pagador)
            transacao.confianca = float(result.get("confianca", 0.5))

            await self.db.commit()

        except Exception as e:
            print(f"Error categorizing transaction: {e}")

        return transacao
