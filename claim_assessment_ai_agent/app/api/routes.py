from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.core.errors import AppError
from app.domain.models import (
    Assessment,
    AttachDocument,
    ChatInput,
    Claim,
    CreateClaim,
    Review,
    ReviewInput,
    now,
    uid,
)
from app.domain.render import markdown_report
from app.services.conversation import ConversationService

router = APIRouter(prefix="/api/v1")


@router.get("/demo-cases")
async def cases(request: Request):
    catalog = request.app.state.catalog
    return [
        {
            "id": c.id,
            "title": c.title,
            "claim": c.claim.model_dump(mode="json"),
            "documents": [d.model_dump(mode="json") for d in c.documents],
        }
        for c in catalog.cases.values()
    ]


@router.post("/sessions", status_code=201)
async def create_session(request: Request):
    session = {"id": uid(), "created_at": now()}
    await request.app.state.db.put("session", session["id"], "", session)
    return session


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    db = request.app.state.db
    session = await db.get("session", session_id)
    return {
        **session,
        "claims": sorted(await db.list("claim", session_id), key=lambda c: c.get("created_at", "")),
        "messages": sorted(await db.list("message", session_id), key=lambda m: m["created_at"]),
    }


@router.post("/claims", response_model=Claim, status_code=201)
async def create_claim(body: CreateClaim, request: Request):
    return await request.app.state.service.create_claim(body)


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str, request: Request):
    service = request.app.state.service
    claim = await service.claim(claim_id)
    return {
        "claim": claim,
        "documents": await service.db.list("document", claim_id),
        "assessments": await service.db.list_runs(claim_id),
    }


@router.post("/claims/{claim_id}/documents", response_model=Claim)
async def attach(claim_id: str, body: AttachDocument, request: Request):
    return await request.app.state.service.add_document(claim_id, body.document_id)


@router.post("/claims/{claim_id}/assessments", response_model=Assessment, status_code=201)
async def assess(claim_id: str, request: Request):
    return await request.app.state.service.assess(claim_id)


@router.get("/assessments/{assessment_id}", response_model=Assessment)
async def get_assessment(assessment_id: str, request: Request):
    return await request.app.state.db.get_run(assessment_id)


@router.get("/assessments/{assessment_id}/tool-calls")
async def trace(assessment_id: str, request: Request):
    db = request.app.state.db
    await db.get_run(assessment_id)
    return sorted(await db.list("tool_call", assessment_id), key=lambda t: t["sequence"])


@router.get("/assessments/{assessment_id}/markdown", response_class=PlainTextResponse)
async def export(assessment_id: str, request: Request):
    run = Assessment.model_validate(await request.app.state.db.get_run(assessment_id))
    if run.report is None:
        raise AppError(409, "assessment_incomplete", "Report is not available")
    return markdown_report(run.report)


@router.get("/assessments/{assessment_id}/reviews", response_model=list[Review])
async def reviews(assessment_id: str, request: Request):
    db = request.app.state.db
    await db.get_run(assessment_id)
    return sorted(await db.list("review", assessment_id), key=lambda r: r["created_at"])


@router.post("/assessments/{assessment_id}/reviews", response_model=Review, status_code=201)
async def review(assessment_id: str, body: ReviewInput, request: Request):
    return await request.app.state.service.review(assessment_id, body)


@router.post("/sessions/{session_id}/messages", status_code=201)
async def message(session_id: str, body: ChatInput, request: Request):
    return await ConversationService(request.app.state.service).message(
        session_id, body.assessment_id, body.content
    )
