from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.models import User, Report
from app.schemas.report import (
    ReportGenerateRequest, ReportResponse, ReportListResponse, ReportTemplateResponse
)
from app.api.deps import get_current_user, get_processo_with_access
from app.services.excel_generator import ExcelGenerator
from app.services.s3_storage import S3Storage

router = APIRouter(prefix="/reports", tags=["reports"])


TEMPLATES = [
    ReportTemplateResponse(
        tipo="transacoes",
        nome="Relatorio de Transacoes",
        descricao="Lista todas as transacoes financeiras com categorias e pagadores",
        parametros=["data_inicio", "data_fim", "categorias", "pagadores"],
    ),
    ReportTemplateResponse(
        tipo="timeline",
        nome="Timeline de Eventos",
        descricao="Linha do tempo dos eventos do processo",
        parametros=["data_inicio", "data_fim"],
    ),
    ReportTemplateResponse(
        tipo="evidencias",
        nome="Relatorio de Evidencias",
        descricao="Compilado de evidencias e documentos do processo",
        parametros=["categorias"],
    ),
]


@router.get("/templates", response_model=list[ReportTemplateResponse])
async def list_templates():
    return TEMPLATES


@router.get("", response_model=ReportListResponse)
async def list_reports(
    processo_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access
    await get_processo_with_access(processo_id, db, current_user)

    query = select(Report).where(Report.processo_id == processo_id)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get reports
    result = await db.execute(
        query.order_by(Report.created_at.desc()).offset(skip).limit(limit)
    )
    reports = result.scalars().all()

    return ReportListResponse(reports=reports, total=total)


@router.post("/excel", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access
    await get_processo_with_access(request.processo_id, db, current_user)

    # Validate tipo
    valid_tipos = [t.tipo for t in TEMPLATES]
    if request.tipo not in valid_tipos:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo invalido. Opcoes: {', '.join(valid_tipos)}",
        )

    # Generate report
    generator = ExcelGenerator(db)
    filename, content = await generator.generate(
        processo_id=request.processo_id,
        tipo=request.tipo,
        data_inicio=request.data_inicio,
        data_fim=request.data_fim,
        categorias=request.categorias,
        pagadores=request.pagadores,
    )

    # Upload to S3
    s3 = S3Storage()
    s3_key = await s3.upload_file(content, filename, request.processo_id, folder="reports")

    # Create report record
    report = Report(
        processo_id=request.processo_id,
        user_id=current_user.id,
        tipo=request.tipo,
        arquivo_s3=s3_key,
        arquivo_nome=filename,
        parametros={
            "data_inicio": str(request.data_inicio) if request.data_inicio else None,
            "data_fim": str(request.data_fim) if request.data_fim else None,
            "categorias": request.categorias,
            "pagadores": request.pagadores,
        },
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")

    # Verify access
    await get_processo_with_access(report.processo_id, db, current_user)

    # Generate presigned URL
    s3 = S3Storage()
    url = await s3.get_presigned_url(report.arquivo_s3)

    return {"download_url": url, "filename": report.arquivo_nome}
