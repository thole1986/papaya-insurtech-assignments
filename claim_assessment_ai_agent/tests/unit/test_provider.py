import pytest
from langchain_core.messages import AIMessage

from app.agent.tools import BenefitArgs
from app.core.errors import AppError
from app.providers.llm import GeminiProvider


async def test_live_tool_adapter_contract_without_network(settings, monkeypatch):
    settings.run_mode = "live"
    settings.google_api_key = "unit-test-placeholder"
    settings.llm_model = "gemini-test-placeholder"
    provider = GeminiProvider(settings)
    args = {"policyId": "POL-DEMO", "claimType": "outpatient", "amount": "1000000"}

    async def response(self, runnable, payload):
        assert payload["required_arguments"] == args
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "unit-call",
                    "name": "calculateBenefit",
                    "args": args,
                }
            ],
        )

    monkeypatch.setattr(GeminiProvider, "_invoke", response)
    try:
        proposal = await provider.propose(
            "calculateBenefit", args, BenefitArgs.model_json_schema(), {}
        )
        assert proposal.name == "calculateBenefit" and proposal.args == args
    finally:
        await provider.aclose()


async def test_sdk_error_text_is_not_exposed(settings):
    settings.run_mode = "live"
    settings.google_api_key = "unit-test-placeholder"
    settings.llm_model = "gemini-test-placeholder"
    provider = GeminiProvider(settings)

    class FailingRunnable:
        async def ainvoke(self, payload):
            raise RuntimeError("https://example.invalid/?key=should-never-leak")

    try:
        with pytest.raises(AppError) as caught:
            await provider._invoke(FailingRunnable(), {"task": "test"})
        assert caught.value.code == "provider_failure"
        assert "should-never-leak" not in caught.value.message
    finally:
        await provider.aclose()
