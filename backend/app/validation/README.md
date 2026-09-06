# Standard Validator – kiểm tra tính toàn vẹn candidate

Điểm gọi: `StandardValidator(evidence_service).validate(plan, student_snapshot, knowledge_snapshot)`.

Bốn rule được bật: course_existence, duplicate_course, catalog_credit_match và prerequisite. Rule bundle dùng phiên bản `integrity-prerequisite-v2`; Validator dùng `standard-integrity-v2`.

Mỗi môn có rule_checks với pass/fail/skipped/error, reason và evidence_ids. Rule chỉ vào checked_rules khi hoàn thành PASS/FAIL cho mọi mã môn; còn SKIPPED/ERROR thì giữ pending. Mọi ràng buộc còn lại trong REQUIRED_RULES vẫn pending; không có nhánh trả valid trong phiên bản này.

- Course không có trong kết quả query thành công: COURSE_NOT_FOUND, invalid. Catalog query lỗi hoặc mã ánh xạ mâu thuẫn: error.
- Duplicate kiểm tra candidate đã normalize mã (trim/uppercase), lưu positions, candidate_plan_id, candidate_plan_version và candidate_plan_hash trong rule_inputs. Không tạo ontology evidence giả.
- Tín chỉ candidate khác catalog: CATALOG_CREDIT_MISMATCH, invalid. Catalog thiếu/mâu thuẫn/không có giá trị số hợp lệ: CATALOG_CREDIT_AMBIGUOUS, error. Các literal biểu diễn cùng giá trị số được coi là nhất quán.
- Course existence fail/error: skip credit và prerequisite; vẫn kiểm tra duplicate và các môn còn lại.
- Prerequisite chỉ đối chiếu completed_courses, không tính môn trong cùng candidate là đã hoàn thành.

Query ID/text/version và triple được giữ trong ontology_evidence; kết luận rule liên kết tới fact gốc. Mã môn được truyền bằng initBindings. Hai query catalog nằm trong knowledge/queries/course_exists.rq và course_credit.rq. Catalog hiện hỗ trợ predicate hasCredit và credit; không dùng ngoại lệ hard-code từ engine làm sự thật ontology.

Kết quả error ưu tiên khi có lỗi thực thi, vẫn giữ violations/evidence đã thu thập. Timestamps có thể khác giữa các lần chạy; kết luận, audit order và định danh dựa trên dữ liệu giữ ổn định. API và Agent chưa được nối vào Validator này.

Chạy kiểm thử: `python -m pytest backend/tests/test_standard_validator.py`.
