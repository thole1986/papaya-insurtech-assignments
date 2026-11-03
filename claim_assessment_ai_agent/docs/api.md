# HTTP API

Base URL mặc định: `http://127.0.0.1:8000`. Swagger: `/docs`, OpenAPI JSON: `/openapi.json`. API của MVP local không có authentication; session/object scoping giữ đúng context nhưng không là access control.

## 1. Endpoints

| Method/path | Success | Contract |
| --- | --- | --- |
| `GET /health` | 200 | Liveness và run mode, không gọi LLM |
| `GET /ready` | 200/503 | Database ready, provider configured, credentials_verified=false |
| `GET /api/v1/demo-cases` | 200 | Case IDs, titles, input preview; không gửi expected vào agent |
| `POST /api/v1/sessions` | 201 | Tạo session, không cần body |
| `GET /api/v1/sessions/{id}` | 200 | Session, claims và messages |
| `POST /api/v1/claims` | 201 | `session_id` và đúng một trong `case_id`/`claim` |
| `GET /api/v1/claims/{id}` | 200 | Current claim, registry documents, assessments |
| `POST /api/v1/claims/{id}/documents` | 200 | Attach trusted registry `document_id`, tăng revision |
| `POST /api/v1/claims/{id}/assessments` | 201 | Chạy graph và trả Assessment envelope; request body không cần |
| `GET /api/v1/assessments/{id}` | 200 | Status, snapshot và report nếu completed |
| `GET /api/v1/assessments/{id}/tool-calls` | 200 | Trace theo sequence, bao gồm rejected/failed |
| `GET /api/v1/assessments/{id}/markdown` | 200 | Plain text Markdown report |
| `POST /api/v1/sessions/{id}/messages` | 201 | `assessment_id`, `content`; trả assistant message |
| `GET /api/v1/assessments/{id}/reviews` | 200 | Append-only review history |
| `POST /api/v1/assessments/{id}/reviews` | 201 | `decision`, `reviewer`, `reason` |

UUIDs của session/claim/assessment khác nhau. Fixture document IDs được prefix claim ID khi import để tạo registry độc lập. Không lấy document ID từ một claim khác để attach.

## 2. Demo bằng PowerShell

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$session = Invoke-RestMethod "$baseUrl/api/v1/sessions" -Method Post
$body = @{ session_id = $session.id; case_id = 'approval_001' } | ConvertTo-Json
$claim = Invoke-RestMethod "$baseUrl/api/v1/claims" -Method Post -ContentType 'application/json' -Body $body
$run = Invoke-RestMethod "$baseUrl/api/v1/claims/$($claim.id)/assessments" -Method Post
$run.report.recommendation
Invoke-RestMethod "$baseUrl/api/v1/assessments/$($run.id)/tool-calls"
```

## 3. Tạo custom claim

```json
{
  "session_id": "<session-id>",
  "claim": {
    "policy_id": "POL-DEMO",
    "member_id": "DEMO-MEMBER",
    "claim_type": "outpatient",
    "amount": "1000000",
    "currency": "VND",
    "diagnosis": "pharyngitis",
    "procedures": ["consultation", "throat_test"],
    "treatment_start": "2026-06-10",
    "treatment_end": "2026-06-10",
    "document_ids": []
  }
}
```

Custom claim bắt đầu chưa có registry documents. Nó sẽ yêu cầu thêm thông tin. Endpoint upload/intake và verifier ngoài fixtures chưa nằm trong MVP; không cho client tự xác nhận giấy tờ. Để demo nộp bổ sung và chuyển outcome, dùng `more_info_003` có available medical report trong registry.

## 4. Assessment envelope và report

Envelope có `id`, `claim_id`, `session_id`, `version`, `status`, `created_at`, immutable `snapshot`, `report`, `error`.

Report có `assessment_id`, `claim_id`, `session_id`, `claim_revision`, `created_at`, `mode`, `model`, `prompt_version` và:

1. `document_review`: từng submitted document và missing required type, status/issues/evidence ID.
2. `policy_verification`: booleans coverage/member/type/waiting và cited findings.
3. `medical_necessity`: status, explanation, rule IDs; NOT_EVALUATED nếu bị dừng trước đó.
4. `benefit_calculation`: submitted, copay, payout, member responsibility, remaining limit; unknown amounts là null.
5. `recommendation`: outcome và reasons chứa code/clause_ids/evidence_refs.
6. `policy_citations`: exact policy clause ID/title/text.

`narrative` là phần diễn giải riêng từ provider, không thay thế structured facts. Tiền là string whole VND. JSON report đầy đủ thực tế xem [`artifacts/offline/approval_001.report.json`](../artifacts/offline/approval_001.report.json).

## 5. Conversation và review

```json
{"assessment_id": "<assessment-id>", "content": "Tại sao hồ sơ này được approve?"}
```

Messages chỉ dùng lịch sử của đúng session **và assessment version**. Chat explanation không chạy tools, không sửa claim/review. Response có role/content/mode/timestamp và assessment ID. History đọc lại qua GET session.

```json
{"decision": "APPROVE", "reviewer": "Demo Assessor", "reason": "Đã kiểm tra evidence và đồng ý payout."}
```

Review cần assessment completed; original recommendation được server điền, không tin từ client. Mỗi request tạo review record mới. Người reviewer là label tự khai trong local demo.

## 6. Errors và retry

Application error shape:

```json
{"error": {"code": "claim_busy", "message": "Assessment is running for this claim"}}
```

| Status | Khi nào |
| --- | --- |
| 404 | Unknown object/policy/case; chat assessment không thuộc session |
| 409 | Concurrent assessment/update, document đã attach, report/review chưa sẵn sàng |
| 422 | Pydantic input validation, foreign document, thiếu usage snapshot đúng treatment year |
| 502 | Provider/tool/structured report validation failure |
| 503 | Live provider chưa cấu hình |
| 504 | Hết timeout tổng assessment/chat |

Pydantic validation dùng shape `detail` chuẩn FastAPI. Với assessment request thất bại sau khi tạo run, xem GET claim → assessments để lấy failed run và trace. Retry tạo assessment version mới; không có idempotency key/resume trong MVP. Không retry liên tục khi request đầu vẫn running.
