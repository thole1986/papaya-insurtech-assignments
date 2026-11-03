# Kiểm thử và evaluation

## 1. Chiến lược

| Layer | Kiểm tra |
| --- | --- |
| Unit domain | Decimal math, rounding half-up, limit cap, copay/member invariants, coverage/waiting boundaries, input/policy validation, medical rules |
| API integration | Health/static/OpenAPI, sessions, claim creation, attachment, reassessment, chat, review, restart persistence, foreign IDs |
| Graph evaluation | Ba expected outcomes, all submitted documents, tool order, early exits, exact policy citations, partial/exhausted benefits |
| Failure injection | Wrong model tool/args, one repair, provider/tool errors, fabricated summary clauses, timeout, concurrency lock, restart recovery |
| Provider contract | Native Gemini binding/response adapter với mocked invocation, safe error masking; không gọi network |

Fake provider được inject qua factory, không đưa expected outcome vào graph. Database mỗi test dùng temporary path riêng. HTTP integration dùng FastAPI TestClient và lifespan thật; không mock graph/domain để ép outcome.

## 2. Quality gates

```powershell
uv sync --locked
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/run_demo.py --mode offline
```

Kết quả chạy cuối cùng xem [implementation-status.md](implementation-status.md). CI workflow chuẩn bị cùng commands trên Windows và Linux; local Windows pass không tự chứng minh GitHub/Linux CI đã pass.

## 3. Evaluation evidence

Script [`scripts/run_demo.py`](../scripts/run_demo.py) gọi API để tạo session/claim, chạy assessment, lấy traces và export artifacts. `--mode` là bắt buộc; output mặc định `artifacts/<mode>`, có thể chọn `--output` directory riêng.

Manifest ghi timestamp UTC, prompt version/hash, lockfile hash, mỗi fixture hash, policy version, model, run ID, từng check và passed tổng. Report chứa sáu sections có schema validate. Trace JSONL có inputs/outputs/errors/status/attempt/timing/mode.

| Case | Tool sequence expected | Business assertions |
| --- | --- | --- |
| Approval | verify × 3 → policy → medical → benefit | APPROVE; payout 800000, member/copay 200000, remaining 3200000 |
| Exclusion | verify × 3 → policy | REJECT theo EXC-COSMETIC; downstream NOT_EVALUATED |
| Missing doc | verify × 2 → policy | REQUEST_MORE_INFO theo DOC-01; missing medical_report |

Mỗi successful graph run đã qua report validator; evaluation kiểm thêm expected outcome, monetary expectations, sequence, submitted-ID coverage và clause membership. Failed provider/tool call không sinh fake successful report.

## 4. Giới hạn bằng chứng

- Offline tests/artifacts không chứng minh model API, credentials, quota hay quality narrative live. Phải có live run với key/model thật trước khi báo live acceptance passed.
- Gemini adapter contract tests chỉ kiểm code path bằng mocked invocation và SDK binding; không gửi request external.
- Static asset/OpenAPI tests không chứng minh layout/JS interactions trong browser. Trong phiên triển khai hiện tại browser/native automation host không khả dụng; visual/interaction QA chưa được xác minh trực tiếp.
- UI manual smoke: cả ba cases, missing-doc attach/reassess, chat, review, history/reload, failed-run error state, màn hình mobile và desktop. Các bước này cần chạy bằng browser khi host khả dụng.
- Model summary/chat vẫn cần human review; deterministic schema/citation checks không là chứng minh ngữ nghĩa cho mọi câu văn model.
