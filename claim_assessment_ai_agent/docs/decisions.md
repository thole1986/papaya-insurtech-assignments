# Architectural decisions và tradeoffs

## ADR-001 — FastAPI + LangGraph, một application process

**Quyết định:** modular monolith async, static UI cùng origin, StateGraph workflow có routing cố định và model tool proposals.

**Lý do:** challenge cần trình tự và auditability rõ; không cần service mesh, React build chain hoặc queue để demo. HTTP, domain và provider vẫn có boundary riêng.

**Hệ quả:** request assessment giữ HTTP connection cho đến khi graph xong; tổng timeout bảo vệ app. Một worker, không hỗ trợ HA. Quy mô lớn cần background jobs, persistent task lifecycle và multi-process locks.

## ADR-002 — uv và Python 3.13

**Quyết định:** giữ venv hiện có, dependency source là pyproject + uv.lock, CI sync locked. SQLAlchemy dùng asyncio extra để có greenlet trên platform thực tế.

**Hệ quả:** setup tái lập, không giữ requirements song song. uv cache local được exclude để tooling không lint third-party source.

## ADR-003 — Deterministic rules giữ quyết định và tiền

**Quyết định:** LLM gọi tool trong stage và viết narrative/chat; code kiểm eligibility, required docs, money, priority và citation mapping.

**Lý do:** outcome và payout cần test được bằng facts, không lệ thuộc model text. Có thể thay provider mà không đổi các invariants.

**Hệ quả:** đây là workflow agent có kiểm soát, không phải agent tự chọn mọi bước. Chi phí nhiều calls do từng submitted doc được kiểm riêng trong live mode; batching có thể tối ưu sau nếu vẫn chứng minh đủ checks.

## ADR-004 — Synthetic registry, không OCR hoặc LLM medical judgment

**Quyết định:** trusted fixture verification + medical table minh bạch. Client không tự ghi actual type/completeness.

**Hệ quả:** demo tái lập và xử lý mismatch đúng, nhưng không thể tự tiếp nhận/xác thực giấy tờ thực hoặc quyết định lâm sàng. Future verifier adapter cần file intake, malware checks, OCR/evidence extraction và nghiệp vụ review thích hợp.

## ADR-005 — SQLite application snapshots, không graph checkpoints

**Quyết định:** lưu snapshot/report/trace/reviews bằng transactions ngắn, startup đánh dấu interrupted runs failed.

**Hệ quả:** review history bền vững, implementation nhỏ. Không durable resume. Nâng cấp multi-worker cần transactional version allocation, database locks/leases và migrations; nếu cần resumability có thể thêm LangGraph checkpointer và idempotent side-effect handling.

## ADR-006 — Partial approval và document-first priority

**Quyết định:** missing required evidence ưu tiên REQUEST_MORE_INFO; amount vượt remaining limit có thể partial approval; exclusion case dùng để minh họa rejection không mơ hồ.

**Lý do:** bám đề và policy fixtures tường minh thay vì suy đoán ý nghĩa limit. Annual limit áp dụng insurer payout sau copay.

**Hệ quả:** assessor thấy cả ineligibility findings khi request-more-info; policy thật phải quy định priority và benefit semantics riêng, không tái dùng giả định demo một cách ngầm định.

## ADR-007 — Honest offline/live evidence

**Quyết định:** offline mode explicit, live không fallback, artifacts/manifest gắn mode và model.

**Hệ quả:** chạy local ngay không key, nhưng không báo hoàn thành live acceptance nếu chưa có API thật. Test doubles không được trình bày như model outputs thật.

## Hướng mở rộng theo nhu cầu

1. Live provider evaluation với key/model thật, kiểm narrative factuality và tool/schema compatibility.
2. Authentication/authorization, audit identity đáng tin cậy và PHI controls trước khi dùng dữ liệu thật.
3. Document intake/verification adapters và policy rule versioning có governance.
4. PostgreSQL/migrations, job queue, locking/reservation ledger và durable graph execution khi cần concurrency/availability.
5. SSE/progress UI và provider batching sau khi có latency/cost measurements.
