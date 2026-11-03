# Data contracts và benefit calculation

## 1. Input và registry

Models tại [`app/domain/models.py`](../app/domain/models.py) đều `extra=forbid`, validate assignment. ClaimInput gồm policy/member IDs, claim type, positive whole-VND amount, diagnosis, procedures, treatment dates và unique document IDs. Không chấp nhận NaN/âm/phần lẻ VND, end trước start hoặc điều trị vượt benefit year; yêu cầu tách claim vượt năm.

Policy chứa effective coverage/lapse dates, members, waiting days, benefits theo claim type, usage year, excluded procedures và registry chín rule clauses. Lapsed status phải có effective lapse date. Historical treatment trước lapse vẫn có thể được bảo hiểm; không lấy status/ngày hôm nay để từ chối hồi tố.

Coverage gồm cả hai biên. Waiting: `treatment_start >= coverage_start + waiting_days`. Usage snapshot phải cùng treatment year nếu cần tính benefit; nếu không có thì calculator trả lỗi dữ liệu 422 và run failed, không dùng số dư năm khác. Claim ngoài coverage vẫn được kiểm policy và REJECT trước khi cần số dư.

Document có declared/actual type, completeness, issues, owner_ref và revision. Registry trong data JSON là trusted demo source. API chỉ attach ID đã có và thuộc claim; không cho client sửa actual type/completeness. Khi import fixture, document IDs và owner_ref được remap sang claim ID mới để không dùng nhầm tài liệu giữa các lần demo.

## 2. Snapshot và versions

| Version | Ý nghĩa |
| --- | --- |
| Claim revision | Tăng khi attach document |
| Assessment version | Tăng mỗi lần đánh giá cùng claim, bao gồm run failed |
| Policy version | Gắn clause IDs và exact lookup terms |
| Document revision | Gắn evidence ID dạng `document:<id>:v<revision>` |
| Medical rule ID/version | Dấu vết bảng quy tắc giả lập |
| Prompt version | Diễn giải và model metadata |

Assessment lưu snapshot riêng trước khi graph chạy. Claim hiện tại có thể ở revision mới trong khi report cũ vẫn thuộc revision cũ. Review luôn trỏ assessment ID cụ thể, không phải “latest claim”.

## 3. Phép tính VND

Policy demo quy định insurer payout annual limit, copay trước cap, không deductible/sub-limit:

```text
copay = round_half_up(submitted_amount × copay_rate, whole VND)
eligible_insurer_amount = submitted_amount - copay
remaining_before = max(annual_limit - used_insurer_payout, 0)
covered_amount = min(eligible_insurer_amount, remaining_before)
limit_excess = eligible_insurer_amount - covered_amount
member_responsibility = copay + limit_excess
remaining_after = remaining_before - covered_amount
```

Tất cả dùng `Decimal`; JSON serialize tiền thành chuỗi. Invariant: payout + member responsibility = submitted amount, payout ≤ remaining_before, mọi số không âm. Assessment không thay đổi used_payout.

Ví dụ case approval: submitted 1.000.000, copay 20%, annual limit 5.000.000, used 1.000.000 → copay/member 200.000, payout 800.000, remaining 3.200.000 VND.

Ví dụ partial approval: submitted 10.000.000 cùng policy → copay 2.000.000, eligible insurer 8.000.000, capped payout 4.000.000, limit excess 4.000.000, total member 6.000.000. Exceeding submitted amount so với limit không đồng nghĩa reject toàn bộ.

Nếu chưa đủ điều kiện gọi calculator, benefit status NOT_EVALUATED, các giá trị chưa biết là null; submitted_amount vẫn hiển thị. Rejection case do exclusion không được hiển thị một payout=0 như thể đã tính.

## 4. Fixture bundles

Mỗi `data/cases/*.json` có claim, policy đầy đủ, submitted documents, available_documents để demo bổ sung và expected riêng cho evaluator. Case 3 không có submitted medical report; available registry document không được xem là đã nộp.

`data/medical_rules.json` chứa bảng giả lập với version trong ID. `scripts/create_fixtures.py` tạo lại dữ liệu minh họa; runtime chỉ đọc fixtures, không dùng generator/expected labels để quyết định.

## 5. Storage

Schema SQLAlchemy nằm tại `app/repositories/database.py`. JSON payload giúp giữ nguyên versioned reports nhưng chưa là schema migration hay normalized financial ledger. Runtime database nằm trong `runtime/` và bị Git ignore. Artifacts được export riêng để review mà không cần chia sẻ DB.
