import asyncio

from app.core.errors import AppError
from app.domain.models import Assessment, now, uid
from app.services.assessment import AssessmentService


class ConversationService:
    def __init__(self, assessments: AssessmentService):
        self.assessments = assessments

    async def message(self, session_id: str, assessment_id: str, content: str) -> dict:
        service = self.assessments
        await service.db.get("session", session_id)
        run = Assessment.model_validate(await service.db.get_run(assessment_id))
        if run.session_id != session_id:
            raise AppError(
                404, "assessment_not_found", "Assessment does not belong to this session"
            )
        if run.status != "completed":
            raise AppError(409, "assessment_incomplete", "Complete an assessment before chatting")
        history = sorted(
            await service.db.list("message", session_id), key=lambda m: m["created_at"]
        )
        # Do not mix reports from different claims/versions into this conversation context.
        history = [m for m in history if m["assessment_id"] == assessment_id]
        provider = service.provider_factory()
        try:
            async with asyncio.timeout(service.settings.assessment_timeout_seconds):
                answer = await provider.chat(run.report, history, content)
        except TimeoutError as exc:
            raise AppError(504, "chat_timeout", "Conversation timed out; please retry") from exc
        finally:
            await provider.aclose()
        items = [
            {
                "id": uid(),
                "session_id": session_id,
                "assessment_id": assessment_id,
                "role": role,
                "content": text,
                "created_at": now(),
                "mode": service.settings.run_mode,
            }
            for role, text in [("user", content), ("assistant", answer)]
        ]
        for message in items:
            await service.db.put("message", message["id"], session_id, message)
        return items[-1]
