# Standard Validator – ràng buộc học vụ

Điểm gọi: `StandardValidator(evidence_service).validate(plan, student_snapshot, knowledge_snapshot)`.
Validator `standard-academic-v3`, rule bundle `academic-constraints-v3`. Không gọi LLM, Generator hoặc Flask.

## Hợp đồng snapshot

KnowledgeSnapshot bổ sung:

- `target_semester_type`: 1 hoặc 2, ánh xạ từ target_term_id và lịch học có phiên bản; không suy từ học kỳ hiện tại. Loại học kỳ khác chưa hỗ trợ.
- `curriculum_courses`: tập mã môn đầy đủ của chương trình ở curriculum_version. None là thiếu dữ liệu, tập rỗng nghĩa là không môn nào thuộc chương trình.
- `prior_study_requirements`: từng mục có course_code và required_courses. Phải có mục cho mỗi môn; tập yêu cầu rỗng là khai báo tường minh không có điều kiện học trước.
- `elective_quotas`: từng mục có category và max_courses (số môn, không phải tín chỉ). Mỗi nhóm tự chọn phải có quota, kể cả quota bằng 0.

Bên tạo snapshot chịu trách nhiệm lấy chính sách từ artifact bất biến tương ứng curriculum/rules/offerings và gắn đúng phiên bản. Chưa có loader xác minh nội dung artifact qua ref. Thay chính sách phải thay phiên bản/snapshot. Ngành và chuyên ngành dùng IRI đầy đủ, không dùng nhãn hiển thị.

## Các rule

- Course existence, duplicate, catalog credit, prerequisite, corequisite, credit limit, completed retake kiểm tra độc lập. Tiên quyết yêu cầu đã hoàn thành; song hành cho phép trong cùng candidate.
- Prior study: môn phải có trong completed/failed hoặc lần học kết thúc passed/failed/exempt. In-progress và môn chỉ nằm trong candidate không thỏa. Đây là quy ước v3 phân biệt học trước với tiên quyết. Lịch sử snapshot phải là dữ liệu trước học kỳ đích; chưa suy thứ tự thời gian từ term ID tùy ý. Ontology chưa có predicate học trước được xác nhận nên điều kiện lấy từ rule snapshot, không tạo triple giả.
- Curriculum membership: môn phải thuộc curriculum_courses và khớp phạm vi ngành/chuyên ngành khai báo trong ontology. Thiếu lựa chọn chuyên ngành khi môn giới hạn chuyên ngành là không đạt.
- Semester offering: so loại học kỳ đích với openSemesterType; 3/12 nghĩa là cả hai kỳ. Thiếu, sai kiểu hoặc mâu thuẫn dữ kiện không được coi là mở cả hai kỳ.
- Elective quota: remaining = max(0, max_courses - số môn completed trong nhóm); số môn phân biệt trong toàn candidate phải <= remaining. Duplicate bị rule riêng loại. Phân nhóm candidate và completed dùng cùng ontology snapshot; thiếu phân loại/quota là lỗi. Môn bắt buộc không tiêu quota. Khai báo đồng thời bắt buộc và tự chọn hiện báo ambiguous, cần phân loại theo chương trình rõ hơn.

## Kết quả và evidence

Mỗi môn có audit pass/fail/skipped/error. Rule còn skipped/error nằm trong pending_rules. Status error ưu tiên khi thiếu dữ liệu/lỗi thực thi, vẫn giữ vi phạm đã tìm thấy. Invalid khi có vi phạm; partially_validated khi còn pending không có lỗi/vi phạm; valid chỉ khi tất cả REQUIRED_RULES đã kiểm tra và đạt.

Evidence chứa rule inputs, candidate hash, snapshot/version và triple/query của fact được sử dụng. Quota lưu ID các fact phân nhóm (bao gồm môn đã hoàn thành) trong rule_inputs và lưu fact gốc trong ontology_evidence. Không nối chúng vào supporting_evidence_ids của môn khác vì schema yêu cầu liên kết trực tiếp cùng môn. Query và ontology có hash nội dung; timestamps có thể khác nhưng kết luận/định danh với cùng đầu vào giữ ổn định.

API và Agent chưa nối vào Validator. Kiểm thử: `python -m pytest backend/tests/test_standard_validator.py`.
