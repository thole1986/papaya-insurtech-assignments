from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.prompts import PROMPT_VERSION
from app.agent.tools import Executor
from app.domain.models import (
    BenefitResult,
    Claim,
    DocumentResult,
    MedicalResult,
    Policy,
    PolicyVerification,
    Report,
    now,
)
from app.domain.rules import (
    decide,
    document_findings,
    required_documents,
    validate_report,
    verify_policy,
)
from app.providers.llm import Provider


class State(TypedDict, total=False):
    claim: Claim
    documents: list[DocumentResult]
    policy: Policy
    verification: PolicyVerification
    medical: MedicalResult
    benefit: BenefitResult
    report: Report


def build_graph(executor: Executor, provider: Provider):
    async def verify_docs(state: State):
        docs = []
        for document_id in state["claim"].document_ids:
            docs.append(await executor.call("verifyDocument", {"documentId": document_id}))
        return {"documents": docs}

    async def policy_lookup(state: State):
        policy = await executor.call("lookupPolicy", {"policyId": state["claim"].policy_id})
        return {"policy": policy}

    def eligibility(state: State):
        claim, policy = state["claim"], state["policy"]
        docs = required_documents(claim, policy, state["documents"])
        verification = verify_policy(claim, policy)
        skip = (
            "Required documents are missing, incomplete or the wrong type."
            if document_findings(policy, claim, docs)
            else "Policy eligibility failed: " + ", ".join(f.code for f in verification.findings)
            if verification.findings
            else "Pending medical necessity."
        )
        return {
            "verification": verification,
            "documents": docs,
            "medical": MedicalResult(
                status="NOT_EVALUATED",
                explanation=skip,
            ),
            "benefit": BenefitResult(
                status="NOT_EVALUATED",
                submitted_amount=claim.amount,
                explanation=skip,
            ),
        }

    def after_eligibility(state: State):
        if (
            document_findings(state["policy"], state["claim"], state["documents"])
            or state["verification"].findings
        ):
            return "compose_report"
        return "check_medical"

    async def medical(state: State):
        claim = state["claim"]
        result = await executor.call(
            "checkMedicalNecessity", {"diagnosis": claim.diagnosis, "procedures": claim.procedures}
        )
        updates = {"medical": result}
        if result.status != "APPROPRIATE":
            updates["benefit"] = BenefitResult(
                status="NOT_EVALUATED",
                submitted_amount=claim.amount,
                explanation=f"Medical necessity result is {result.status}; benefit stage skipped.",
            )
        return updates

    async def benefit(state: State):
        claim = state["claim"]
        result = await executor.call(
            "calculateBenefit",
            {
                "policyId": claim.policy_id,
                "claimType": claim.claim_type,
                "amount": str(claim.amount),
            },
        )
        return {"benefit": result}

    async def compose(state: State):
        claim, policy = state["claim"], state["policy"]
        recommendation = decide(
            claim,
            policy,
            state["documents"],
            state["verification"],
            state["medical"],
            state["benefit"],
        )
        ids = {c for reason in recommendation.reasons for c in reason.clause_ids}
        report = Report(
            assessment_id=executor.run_id,
            claim_id=claim.id,
            session_id=claim.session_id,
            claim_revision=claim.revision,
            created_at=now(),
            mode=executor.mode,
            model=provider.model,
            prompt_version=PROMPT_VERSION,
            document_review=state["documents"],
            policy_verification=state["verification"],
            medical_necessity=state["medical"],
            benefit_calculation=state["benefit"],
            recommendation=recommendation,
            policy_citations=[c for c in policy.clauses.values() if c.id in ids],
        )
        feedback = ""
        for attempt in (1, 2):
            try:
                narrative = await provider.summarize(report, feedback)
                if sorted(narrative.reason_codes) != sorted(
                    r.code for r in recommendation.reasons
                ) or sorted(narrative.clause_ids) != sorted(ids):
                    raise ValueError("Model summary citation/reason identifiers differ from facts")
                report.narrative = narrative.summary
                break
            except ValueError:
                if attempt == 2:
                    raise
                feedback = "Return exactly the report's reason codes and union of clause IDs."
        return {"report": report}

    def validate(state: State):
        validate_report(
            state["report"],
            state["claim"],
            state["policy"],
            state["documents"],
            state["medical"],
            state["benefit"],
        )
        return {}

    graph = StateGraph(State)
    for name, node in [
        ("verify_documents", verify_docs),
        ("lookup_policy", policy_lookup),
        ("eligibility", eligibility),
        ("check_medical", medical),
        ("calculate_benefit", benefit),
        ("compose_report", compose),
        ("validate", validate),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "verify_documents")
    graph.add_edge("verify_documents", "lookup_policy")
    graph.add_edge("lookup_policy", "eligibility")
    graph.add_conditional_edges(
        "eligibility", after_eligibility, ["check_medical", "compose_report"]
    )
    graph.add_conditional_edges(
        "check_medical",
        lambda s: "calculate_benefit" if s["medical"].status == "APPROPRIATE" else "compose_report",
        ["calculate_benefit", "compose_report"],
    )
    graph.add_edge("calculate_benefit", "compose_report")
    graph.add_edge("compose_report", "validate")
    graph.add_edge("validate", END)
    return graph.compile()
