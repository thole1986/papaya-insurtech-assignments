# Trạng thái triển khai và bàn giao

Ngày: **02/11/2026**. Nền tảng xác minh local: Windows, Python **3.13.13**, uv **0.9.13**. Không thay venv, không dùng pip.

## 1. Phase mapping

| Phase | Phần đã triển khai | Bằng chứng / giới hạn |
| --- | --- | --- |
| P0 | pyproject, uv.lock, settings, FastAPI factory/lifespan, health/readiness, SQLite, static UI | `uv sync --locked` pass; Uvicorn startup thành công; API health/static/OpenAPI tests pass |
| P1 | Typed models, ba fixtures đầy đủ, four tools, money/eligibility/document/citation rules | Unit và evaluation tests pass, bao gồm limits/rounding/wrong document type |
| P2 | LangGraph conditional flow, stage executor, Gemini native tool/structured-output adapter, fake explicit, validators/timeouts | Graph/failure tests và SDK adapter contract tests pass; chưa có API key/model để live smoke |
| P3 | REST API, snapshots, trace persistence, conversations, document revisions, assessor review | API end-to-end và restart/concurrency/session-scoping tests pass |
| P4 | Same-origin responsive UI: case/custom claim, report, trace, history, supplementation, chat/review | Static routes và JS syntax pass; browser/native automation host không khả dụng, chưa visual/interaction QA |
| P5 | Evaluation exporter, offline artifacts/manifest, README, design/operations/API/testing docs, CI workflow | Ba cases offline pass; source sẵn sàng review; chưa live API evaluation/GitHub push |

## 2. Checks đã chạy

- `uv sync --locked`: pass, dùng lockfile trên Python 3.13 hiện có.
- `uv lock --check`: pass.
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass.
- `uv run pytest -q`: **48 passed**.
- `node --check app/static/app.js`: pass (chỉ syntax check, không browser interaction).
- `uv run python scripts/run_demo.py --mode offline`: **3/3 cases PASS**.
- `uv run python scripts/run_demo.py --mode live`: dừng rõ ràng vì thiếu key/model, không fallback và không tạo live report giả.
- Uvicorn đã khởi động và báo application startup complete trên loopback; không suy ra browser QA từ startup log.

Artifacts thực tế: [offline manifest](../artifacts/offline/manifest.json), [approval report](../artifacts/offline/approval_001.report.json), [rejection report](../artifacts/offline/rejection_002.report.json), [missing-doc report](../artifacts/offline/more_info_003.report.json). Tool logs và input snapshots ở cùng thư mục.

## 3. Phần cần điều kiện bên ngoài

1. **Live acceptance:** điền key/model Gemini trong `.env`, chạy live evaluation và review narrative/trace. Adapter đã implement nhưng chưa xác minh request API thật.
2. **UI acceptance:** mở browser local và thực hiện manual smoke theo `docs/testing.md`. Trong phiên này browser access host và native automation pipe đều unavailable.
3. **GitHub:** workspace ban đầu chưa là Git repository và chưa có remote; chưa push hoặc chạy hosted CI. Workflow đã có, nhưng không báo CI cloud passed.
4. **Production:** authentication/authorization, real document intake/verifier/medical rules, migrations, multi-worker/ledger nằm ngoài MVP theo thiết kế.

Các giới hạn này không được gộp thành trạng thái “đã chạy live đầy đủ”. Để demo ngay không key, dùng offline mode được gắn nhãn rõ trong UI/report/artifacts.
