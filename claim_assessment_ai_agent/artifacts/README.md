# Evaluation artifacts

`offline/` chứa outputs do API + LangGraph thật chạy với **fake provider explicit**. Không có LLM API request. Medical/document tools dùng synthetic fixtures.

Mỗi case gồm report JSON/Markdown, tool call JSONL và snapshot. `manifest.json` ghi checks, mode/model, prompt/fixture/lockfile hashes. Sinh lại bằng:

```powershell
uv run python scripts/run_demo.py --mode offline
```

Khi đã cấu hình key/model thật:

```powershell
uv run python scripts/run_demo.py --mode live --output artifacts/live/my-run
```

Không có live output được tạo sẵn nếu chưa thực thi LLM API thật. Review artifacts chứa synthetic data trước khi commit; không export claims thực/keys vào repository.
