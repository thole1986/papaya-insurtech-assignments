# Claim Assessment AI Agent

MVP thẩm định hồ sơ bảo hiểm bằng **FastAPI + LangGraph**, Python **3.13**, quản lý bằng **uv**. Có UI, hội thoại theo session, bốn tools, structured report có policy citations, audit trace và assessor review độc lập.

Ứng dụng khởi động mặc định ở **offline mode** để demo ngay, không cần API key. Đây là fake provider được gắn nhãn rõ; chuyển sang **live mode** để dùng Gemini tool calling và structured output thật. Document verification và medical rules là fixture giả lập ở cả hai mode.

## Chạy nhanh trên Windows

Từ thư mục project, dùng `.venv` Python 3.13 đã có:

```powershell
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở [ứng dụng](http://127.0.0.1:8000) hoặc [Swagger](http://127.0.0.1:8000/docs). Không cần activate venv hay cài pip. `uv.toml` đặt cache trong project; Ruff và Git đã loại cache khỏi source.

Luồng demo:

1. Chọn một case, bấm **Tạo hồ sơ từ case**, sau đó **Chạy assessment**.
2. Xem sáu phần report, clause text, payout và tool execution trace.
3. Hỏi tiếp ở conversation. Offline mode trả lời theo mẫu; live mode dùng LLM.
4. Với `more_info_003`, chọn `medical_report` ở mục bổ sung tài liệu, tạo revision rồi đánh giá lại: `REQUEST_MORE_INFO` → `APPROVE`.
5. Ghi tên assessor, quyết định và lý do review. Review không sửa recommendation gốc.

## Bật LLM thật

```powershell
Copy-Item .env.example .env
```

Chỉnh `.env` cục bộ:

```dotenv
RUN_MODE=live
GOOGLE_API_KEY=<your-key>
LLM_MODEL=<available-gemini-model-with-tool-calling>
```

Restart server. UI phải hiển thị `LIVE · GEMINI API`. Model ID không hardcode vì khả dụng phụ thuộc tài khoản/thời điểm. Key chỉ đọc từ environment/`.env`, không nhập qua UI. Không commit `.env`.

```powershell
uv run python scripts/run_demo.py --mode live
```

Thiếu cấu hình live trả lỗi rõ ràng, không tự dùng fake. `/ready` kiểm tra database và cấu hình, không xác minh key/model với provider.

## Kiểm tra và evaluation

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/run_demo.py --mode offline
```

Script đi qua HTTP routes bằng ASGI TestClient và LangGraph thật, xuất vào `artifacts/<mode>/`: JSON/Markdown report, JSONL tool calls, input snapshot và manifest chứa hashes/checks. Không cần server đang chạy. Mỗi lần chạy dùng database evaluation riêng trong `runtime/`.

| Case | Outcome | Insurer payout | Tool calls thành công |
| --- | --- | --- | --- |
| `approval_001` | APPROVE | 800.000 VND | 3 document checks + policy + medical + benefit |
| `rejection_002` | REJECT | Chưa tính do exclusion | 3 document checks + policy |
| `more_info_003` | REQUEST_MORE_INFO | Chưa tính do thiếu medical report | 2 document checks + policy |

Số tiền chưa tính là `null`, không giả thành 0. Mọi tài liệu đã nộp đều được verify. Nhánh dừng sớm thể hiện `NOT_EVALUATED` để tránh tool calls không cần thiết.

## Cấu trúc và tài liệu

```text
app/api/             HTTP contracts
app/agent/           LangGraph, prompts, tool schemas/executor
app/domain/          Typed models, deterministic rules, report rendering
app/providers/       Gemini adapter, explicit offline test double
app/repositories/    SQLite storage, trusted fixture catalog
app/services/        Assessment/revision, conversation, human review
app/static/          Same-origin HTML/CSS/JavaScript UI
data/                3 complete synthetic case bundles + medical rules
tests/               Unit, API integration, graph/evaluation/failure tests
scripts/             Fixture generator and evaluation exporter
docs/                Architecture, decisions, API, data, operations and validation
artifacts/offline/   Generated evidence; clearly marked offline
```

Bắt đầu tại [docs/README.md](docs/README.md). Kế hoạch gốc ở [plan.md](plan.md); tình trạng bàn giao ở [docs/implementation-status.md](docs/implementation-status.md).

## Phạm vi thực tế

- Local, **một process/worker**, synthetic data; chưa có authentication hay tenant authorization. Session IDs dùng để giữ context, không phải access control.
- Không OCR, xác minh giấy tờ thực, y khoa production hay thanh toán. Client chỉ được attach document ID từ registry của chính claim; không tự gửi `complete=true` để vượt verification.
- Custom JSON dùng policy đã có và bắt đầu không có tài liệu. MVP chỉ bổ sung tài liệu đã tồn tại trong registry fixture; tiếp nhận/tạo verification hồ sơ ngoài registry là phần mở rộng.
- SQLite giữ report/snapshot/log/review qua restart, không resume graph dang dở. Run đang chạy lúc restart được đánh dấu failed.
- Deterministic report fields được validate; phần diễn giải/chat từ LLM vẫn cần assessor đọc cùng evidence.
- Source và offline artifacts đã chuẩn bị để nộp. Live evaluation cần API key/model; GitHub push cần repository remote/quyền truy cập. Không coi các phần này là đã thực hiện khi thiếu điều kiện.
