"""Exercise the real HTTP routes/graph and export synthetic evaluation evidence."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.domain.models import Report, now, uid  # noqa: E402
from app.domain.render import markdown_report  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.fixtures import Catalog  # noqa: E402


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["offline", "live"], required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings(
        run_mode=args.mode,
        database_url=f"sqlite+aiosqlite:///{ROOT / 'runtime' / ('eval-' + uid() + '.db')}",
    )
    if not settings.provider_ready:
        print("Live evaluation requires GOOGLE_API_KEY and LLM_MODEL. No fallback performed.")
        return 2
    output = args.output or ROOT / "artifacts" / args.mode
    output.mkdir(parents=True, exist_ok=True)
    catalog = Catalog()
    manifest = {
        "created_at": now(),
        "mode": args.mode,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": digest(SYSTEM_PROMPT.encode()),
        "lockfile_sha256": digest((ROOT / "uv.lock").read_bytes()),
        "cases": [],
    }
    with TestClient(create_app(settings)) as client:
        for case in catalog.cases.values():
            session = client.post("/api/v1/sessions").json()
            claim = client.post(
                "/api/v1/claims", json={"session_id": session["id"], "case_id": case.id}
            ).json()
            response = client.post(f"/api/v1/claims/{claim['id']}/assessments")
            fixture_hash = digest((ROOT / "data/cases" / f"{case.id}.json").read_bytes())
            entry = {
                "case_id": case.id,
                "fixture_sha256": fixture_hash,
                "policy_version": case.policy.version,
                "passed": False,
            }
            if response.status_code == 201:
                run = response.json()
                report = Report.model_validate(run["report"])
                traces = client.get(f"/api/v1/assessments/{run['id']}/tool-calls").json()
                actual = report.model_dump(mode="json")
                expected_names = ["verifyDocument"] * len(claim["document_ids"]) + ["lookupPolicy"]
                if case.expected["outcome"] == "APPROVE":
                    expected_names += ["checkMedicalNecessity", "calculateBenefit"]
                checks = {
                    "outcome": report.recommendation.outcome == case.expected["outcome"],
                    "tool_sequence": [t["tool"] for t in traces if t["status"] == "completed"]
                    == expected_names,
                    "all_documents": [
                        t["inputs"]["documentId"]
                        for t in traces
                        if t["tool"] == "verifyDocument" and t["status"] == "completed"
                    ]
                    == claim["document_ids"],
                    "citations": bool(report.policy_citations)
                    and all(
                        c in {v.id for v in case.policy.clauses.values()}
                        for r in report.recommendation.reasons
                        for c in r.clause_ids
                    ),
                }
                for key, value in case.expected.items():
                    if key != "outcome":
                        checks[key] = actual["benefit_calculation"][key] == value
                entry.update(
                    passed=all(checks.values()),
                    checks=checks,
                    model=report.model,
                    assessment_id=run["id"],
                )
                (output / f"{case.id}.report.json").write_text(
                    json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                (output / f"{case.id}.report.md").write_text(
                    markdown_report(report), encoding="utf-8"
                )
                (output / f"{case.id}.tools.jsonl").write_text(
                    "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces),
                    encoding="utf-8",
                )
                (output / f"{case.id}.snapshot.json").write_text(
                    json.dumps(run["snapshot"], indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            else:
                entry["error"] = response.json()
            manifest["cases"].append(entry)
            print(f"{case.id}: {'PASS' if entry['passed'] else 'FAIL'} ({args.mode})")
    manifest["passed"] = all(c["passed"] for c in manifest["cases"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
