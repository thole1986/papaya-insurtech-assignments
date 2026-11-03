# Vận hành và development workflow

## 1. Bootstrap bằng uv

Yêu cầu Python 3.13 và uv. `.venv` đã có được giữ nguyên. Không cần pip/activation.

```powershell
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Phát triển có thể thêm `--reload`; demo ổn định dùng lệnh trên. Chỉ một worker. Dừng bằng Ctrl+C. Không chạy hai server khác port trỏ cùng database, vì startup recovery sẽ đánh dấu running runs của process kia là interrupted.

`uv.toml` dùng cache local `.uv-cache-clean` do giới hạn filesystem môi trường phát triển; cache bị Git/Ruff ignore. Thay dependency dùng `uv add`/`uv add --dev`, review lockfile; không sửa requirements thủ công. `requirements.txt` trống có sẵn được giữ để không xóa file của người dùng, nhưng không được dùng để cài app.

## 2. Cấu hình

| Variable | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `RUN_MODE` | `offline` | `offline` fake provider, hoặc `live` Gemini |
| `GOOGLE_API_KEY` | Trống | Secret API key, bắt buộc cho live |
| `LLM_MODEL` | Trống | Model khả dụng hỗ trợ tools/structured output, bắt buộc live |
| `DATABASE_URL` | `sqlite+aiosqlite:///./runtime/claims.db` | Async SQLite URL |
| `ASSESSMENT_TIMEOUT_SECONDS` | 180 | Tổng graph/chat budget |
| `PROVIDER_TIMEOUT_SECONDS` | 30 | Mỗi LLM request |

Settings đọc `.env` ở project root; environment có precedence. Copy `.env.example` sang `.env` rồi chỉnh cục bộ, không paste key vào docs/UI/logs. Restart để nhận config mới. Live data gửi Gemini chỉ nên là fixtures synthetic trong phạm vi MVP.

## 3. Live smoke/evaluation

1. Cấu hình key và model từ tài khoản Gemini.
2. Chạy `/ready`: configured=true chỉ xác nhận có cấu hình, chưa kiểm chứng credentials.
3. Chạy `uv run python scripts/run_demo.py --mode live`.
4. Kiểm tra exit code 0 và `artifacts/live/manifest.json` có mode=live, model thực và ba cases passed.
5. Review reports/trace/narrative; không coi offline artifacts là bằng chứng gọi API thật.

Thiếu key/model: script exit 2 trước khi tạo live evidence. Provider lỗi: không fallback, run failed, manifest ghi failure. Trước khi nộp nên dùng output directory mới (`--output artifacts/live/<run-name>`) để tránh trộn artifacts cũ và mới.

## 4. Database và backup

SQLite bật WAL. Runtime logs/data trong `runtime/`, không đưa lên Git. Dừng app trước khi copy backup database để tránh bỏ sót WAL. Không tự xóa DB để sửa lỗi schema; cần migration hoặc giữ backup rồi tạo database demo mới với URL mới.

Startup chỉ khởi tạo tables chưa tồn tại và recover running runs; không migrate columns. Completed reports, traces, messages và reviews đọc lại sau restart. In-flight graph không resume; retry thành version mới. Assessment không thanh toán hay trừ số dư benefit.

Evaluation tạo DB riêng tên `eval-<uuid>.db`. Có thể lưu DB này để điều tra run, còn artifacts là bản xuất phục vụ submission. Dữ liệu demo và cache không có retention automation trong MVP.

## 5. Troubleshooting

| Triệu chứng | Kiểm tra / xử lý |
| --- | --- |
| uv cache access denied | Chạy từ root để nhận `uv.toml`; dùng cache trong workspace |
| Dependency download bị sandbox/network block | Dùng quyền network phù hợp cho `uv sync`; không đổi sang pip |
| SQLAlchemy thiếu greenlet | `uv sync --locked`; project khai báo `sqlalchemy[asyncio]` |
| Port 8000 đang dùng | Dừng server cũ hoặc chọn port khác với DB riêng |
| 503 provider_not_configured | Kiểm RUN_MODE, key/model được điền; restart |
| 502 provider_failure | Kiểm key, model availability/quota/network trong provider account; logs app không in upstream secret URL |
| 409 claim_busy | Chờ run hiện tại; không đồng thời attach và assess |
| REQUEST_MORE_INFO dù thấy document trong registry | Registry available chưa đồng nghĩa submitted; attach rồi reassess |
| UI còn report revision cũ | Xem assessment history; bổ sung docs chỉ tạo revision, chưa tự chạy assessment |
| Run failed sau restart | Hành vi recovery dự kiến; chạy assessment version mới |

## 6. GitHub submission

Repo ban đầu chưa có Git remote. Source có CI workflow nhưng chưa thể khẳng định CI đã chạy trên GitHub. Khi có repository và quyền truy cập: review `.gitignore`, kiểm `.env`/DB/cache không bị stage, commit source/uv.lock/docs/fixture artifacts phù hợp, thêm remote và push. Không đưa API key vào commit để demo live.

CI chạy Python 3.13 trên Windows/Linux, uv sync locked, lint/format/tests và offline evaluation. Live evaluation không chạy mặc định trong CI và không cần GitHub secrets cho offline suite.
