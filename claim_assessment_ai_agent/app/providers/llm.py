import asyncio
import json
from typing import Protocol

from app.agent.prompts import SYSTEM_PROMPT
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.models import Narrative, Report, ToolProposal


class Provider(Protocol):
    model: str
    usage: list[dict]

    async def propose(
        self, name: str, args: dict, schema: dict, context: dict, feedback: str = ""
    ) -> ToolProposal: ...

    async def summarize(self, report: Report, feedback: str = "") -> Narrative: ...

    async def chat(self, report: Report, history: list[dict], content: str) -> str: ...

    async def aclose(self) -> None: ...


class OfflineProvider:
    """Explicit deterministic test double. Does not call an LLM API."""

    model = "offline-deterministic-v1"

    def __init__(self):
        self.usage: list[dict] = []

    async def aclose(self) -> None:
        pass

    async def propose(
        self, name: str, args: dict, schema: dict, context: dict, feedback: str = ""
    ) -> ToolProposal:
        return ToolProposal(name=name, args=args)

    async def summarize(self, report: Report, feedback: str = "") -> Narrative:
        reasons = report.recommendation.reasons
        return Narrative(
            summary=f"[Offline demo] {report.recommendation.outcome}: "
            + " ".join(r.explanation for r in reasons),
            reason_codes=[r.code for r in reasons],
            clause_ids=sorted({c for r in reasons for c in r.clause_ids}),
        )

    async def chat(self, report: Report, history: list[dict], content: str) -> str:
        reasons = "\n".join(
            f"{r.explanation} [{', '.join(r.clause_ids)}]" for r in report.recommendation.reasons
        )
        benefit = report.benefit_calculation
        payout = benefit.covered_amount if benefit.covered_amount is not None else "chưa đánh giá"
        return (
            f"[Offline demo: phản hồi theo mẫu, không dùng LLM]\n"
            f"Đề xuất: {report.recommendation.outcome}\n{reasons}\n"
            f"Insurer payout: {payout} VND.\n"
            "Dùng mục bổ sung tài liệu để tạo revision mới; "
            "dùng mục assessor review để ghi quyết định."
        )


class GeminiProvider:
    def __init__(self, settings: Settings):
        if not settings.provider_ready:
            raise AppError(
                503, "provider_not_configured", "Set GOOGLE_API_KEY and LLM_MODEL for live mode"
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model = settings.llm_model
        self.timeout = settings.provider_timeout_seconds
        self.usage: list[dict] = []
        self.client = ChatGoogleGenerativeAI(
            model=self.model,
            api_key=settings.google_api_key,
            vertexai=False,
            temperature=0,
            max_retries=0,
            timeout=self.timeout,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _invoke(self, runnable, payload: dict):
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            async with asyncio.timeout(self.timeout):
                response = await runnable.ainvoke(
                    [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                    ]
                )
        except Exception as exc:
            # Never include SDK exception text: upstream URLs may contain credentials.
            raise AppError(502, "provider_failure", "LLM request failed or timed out") from exc
        raw = response.get("raw") if isinstance(response, dict) else response
        usage = getattr(raw, "usage_metadata", None)
        if usage:
            self.usage.append(dict(usage))
        return response

    async def propose(
        self, name: str, args: dict, schema: dict, context: dict, feedback: str = ""
    ) -> ToolProposal:
        tool = {
            "name": name,
            "description": f"Execute {name} for the current assessment stage.",
            "parameters": schema,
        }
        response = await self._invoke(
            self.client.bind_tools([tool], tool_choice="any"),
            {
                "task": "Call exactly this allowed tool with these required arguments.",
                "allowed_tool": name,
                "required_arguments": args,
                "verified_context": context,
                "validation_feedback": feedback,
            },
        )
        calls = response.tool_calls
        if len(calls) != 1:
            return ToolProposal(name="INVALID_CALL_COUNT", args={})
        return ToolProposal(name=calls[0]["name"], args=calls[0]["args"])

    async def summarize(self, report: Report, feedback: str = "") -> Narrative:
        response = await self._invoke(
            self.client.with_structured_output(Narrative, include_raw=True),
            {
                "task": "Summarize this immutable report. Return every recommendation reason code "
                "and the union of its clause IDs exactly. Do not add facts.",
                "report": report.model_dump(mode="json"),
                "validation_feedback": feedback,
            },
        )
        if response.get("parsed") is None:
            raise ValueError("Invalid structured model response")
        return Narrative.model_validate(response["parsed"])

    async def chat(self, report: Report, history: list[dict], content: str) -> str:
        response = await self._invoke(
            self.client,
            {
                "task": "Answer about the report using its evidence and exact clause citations.",
                "report": report.model_dump(mode="json"),
                "history": history[-20:],
                "question": content,
            },
        )
        if isinstance(response.content, str):
            return response.content
        return "\n".join(b.get("text", "") for b in response.content if isinstance(b, dict))


def make_provider(settings: Settings) -> Provider:
    return OfflineProvider() if settings.run_mode == "offline" else GeminiProvider(settings)
