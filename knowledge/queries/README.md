# Truy vấn ontology

`prerequisites.rq`: Q_PREREQ_01, truy xuất quan hệ `hasPrerequisiteCourse`. Subject được truyền qua initBindings; mã người dùng không được ghép vào câu SPARQL.

OntologyEvidenceService giữ graph riêng từ nội dung RDF/XML đã đọc. Phiên bản ontology là SHA-256 bytes nguồn; query_version là SHA-256 nội dung query. Không đồng nhất tên file v23 với content version.

Kết quả trả OntologyFactEvidence, không phải kết luận validity. Môn không tồn tại/không rõ mã hoặc version không khớp gây lỗi. Query không có quan hệ trả kết quả rỗng cho môn tồn tại; đây chỉ là sự vắng mặt trong snapshot, không chứng minh ontology đầy đủ.

Rule PREREQ_COMPLETED_01 nằm trong backend/app/validation/prerequisite_rule.py, phiên bản integrity-prerequisite-v2. Rule đối chiếu completed_courses, trả EvidenceRecord có liên kết fact, query, triple và KnowledgeVersion. Chưa là Standard Validator cho toàn kế hoạch; chưa kết nối API hiện tại.

Bên gọi phải lưu cả fact và kết luận rule để giữ query_version và đầy đủ provenance. Kiểm thử: python -m pytest backend/tests/test_ontology_evidence.py.

Q_COURSE_01 (course_exists.rq) tra mã môn; Q_CREDIT_01 (course_credit.rq) tra tín chỉ qua hasCredit/credit. Môn không tồn tại có fact kết quả rỗng; catalog thiếu/mâu thuẫn tín chỉ gây lỗi nguồn.
