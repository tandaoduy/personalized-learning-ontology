# ĐẶC TẢ NGHIỆP VỤ AI AGENT LẬP KẾ HOẠCH HỌC TẬP

> Nguồn: [TÀI LIỆU THIẾT KẾ AI AGENT LẬP KẾ HOẠCH HỌC TẬP.pdf](<TÀI LIỆU THIẾT KẾ AI AGENT LẬP KẾ HOẠCH HỌC TẬP.pdf>). Bản này trình bày các yêu cầu nghiệp vụ theo PDF; thiết kế và thực nghiệm đầy đủ xem [tài liệu thiết kế](THIET_KE_AI_AGENT.md).

## 1. Bối cảnh

Kế hoạch học kỳ phải phù hợp hồ sơ, mục tiêu người học và đồng thời tuân thủ chương trình đào tạo, tiên quyết, học trước, song hành, học kỳ mở, tín chỉ và tình trạng học vụ.

Hệ thống hiện có ontology và bộ máy gợi ý. AI Agent phát triển tiếp sẽ tiếp nhận mục tiêu, sinh nhiều phương án, kiểm tra, giải thích và lập lại theo phản hồi. Ontology và Rule Engine quyết định tính đúng; Agent không tự tạo môn, tín chỉ, quan hệ hoặc quy định học vụ.

## 2. Mục tiêu

- Đề xuất tối đa ba kế hoạch cá nhân hóa.
- Chỉ hiển thị phương án vượt kiểm tra học vụ.
- Giải thích việc chọn/loại môn bằng căn cứ.
- Cho phép lựa chọn, chỉnh sửa và lập lại.
- Thu thập phản hồi để cải thiện xếp hạng.
- Hỗ trợ đánh giá nghiên cứu định lượng.

## 3. Các bên liên quan

| Bên liên quan | Vai trò |
|---|---|
| Sinh viên | Cung cấp mục tiêu, so sánh, chọn hoặc điều chỉnh |
| Cố vấn | Đánh giá, xếp hạng, chỉnh sửa và xác nhận |
| AI Agent | Điều phối lập kế hoạch, kiểm tra, giải thích và lập lại |

Phương án được người dùng chấp nhận phải qua Final Validation trên phiên bản dữ liệu hiện hành trước khi xác nhận.

## 4. Dữ liệu đầu vào

### 4.1. Hồ sơ sinh viên

- Mã sinh viên, ngành, chuyên ngành và CTĐT.
- Học kỳ, bảng điểm và lịch sử các lần học.
- GPA, tín chỉ, môn chưa đạt/học lại.
- Cảnh báo học vụ.

### 4.2. Tri thức đào tạo

- Khung CTĐT; môn bắt buộc, tự chọn, nhóm chuyên ngành.
- Tiên quyết, học trước, song hành.
- Tín chỉ, học kỳ khuyến nghị và học kỳ mở.
- Giới hạn tín chỉ và quy tắc học vụ.

### 4.3. Yêu cầu và phản hồi

- Học kỳ, mục tiêu, tín chỉ mong muốn.
- Môn ưu tiên hoặc tránh.
- Lựa chọn/xếp hạng A/B/C.
- Yêu cầu thêm, loại, thay thế và lý do.

## 5. Mục tiêu lập kế hoạch

| Mục tiêu | Mô tả |
|---|---|
| Hoàn thành đúng hạn | Ưu tiên môn bắt buộc và tháo gỡ nút thắt |
| Học vượt tiến độ | Đề xuất học trước tiến độ khi sinh viên đã đáp ứng đầy đủ các điều kiện học vụ |

Mục tiêu định hướng xếp hạng nhưng không thay đổi ràng buộc bắt buộc.

## 6. Ba loại phương án

| Phương án | Định hướng |
|---|---|
| Safe – An toàn | Tải vừa phải, ưu tiên môn nợ, giảm rủi ro |
| Balanced – Cân bằng | Bám tiến độ chuẩn, cân đối tải và nhóm môn |
| Accelerated – Học vượt | Đề xuất học trước tiến độ khi sinh viên đã đáp ứng đầy đủ các điều kiện học vụ |

Nếu không đủ ba phương án hợp lệ, hệ thống trả phương án hiện có và giải thích nguyên nhân; không nới luật để tạo đủ ba phương án. Mọi cặp phương án Top-3 phải đạt ngưỡng khác biệt được xác định trong giai đoạn validation, với D = 1 − Jaccard trên tập học phần. Khi điểm Ranking gần nhau nhưng danh sách môn quá giống nhau, ưu tiên phương án khác biệt hơn.

## 7. Luồng nghiệp vụ

1. Người dùng chọn học kỳ, mục tiêu và tín chỉ.
2. Hệ thống tải, kiểm tra hồ sơ.
3. Đối chiếu CTĐT để xác định môn phù hợp.
4. Sinh phương án theo ba định hướng.
5. Kiểm tra toàn bộ ràng buộc.
6. Loại hoặc sinh lại phương án sai.
7. Xếp hạng phương án hợp lệ, chọn Top-3.
8. Trình bày môn, tín chỉ, cảnh báo và lý do.
9. Người dùng chọn, xếp hạng hoặc điều chỉnh.
10. Kế hoạch điều chỉnh được sinh và kiểm tra lại.
11. Phương án chọn qua kiểm tra cuối rồi xác nhận.
12. Lưu kế hoạch và phản hồi.

## 8. Quy tắc nghiệp vụ

| Mã | Quy tắc |
|---|---|
| BR-01 | Ontology và Rule Engine là nguồn quyết định tính hợp lệ |
| BR-02 | Môn phải tồn tại và thuộc đúng CTĐT/chuyên ngành |
| BR-03 | Môn được mở trong học kỳ mục tiêu |
| BR-04 | Thỏa tiên quyết, học trước và song hành |
| BR-05 | Tuân thủ giới hạn tín chỉ và cảnh báo học vụ |
| BR-06 | Mục tiêu đúng hạn ưu tiên môn bắt buộc và tháo gỡ nút thắt |
| BR-07 | Học vượt chỉ khi đáp ứng đầy đủ điều kiện học vụ |
| BR-08 | Kiểm tra môn đã hoàn thành, học lại/cải thiện |
| BR-09 | Tuân thủ quota và nhóm môn tự chọn |
| BR-10 | Quyết định liên quan học phần có evidence từ Ontology, SPARQL hoặc Rule Engine; explanation tham chiếu evidence_id |
| BR-11 | Chỉ phương án qua Validation mới được xếp hạng, giải thích và hiển thị |
| BR-12 | Sau phản hồi hoặc Re-planning, phương án phải được Validation lại |
| BR-13 | Ranking/LTR chỉ đổi thứ tự ưu tiên, không ghi đè Validator hoặc sửa hard constraints |
| BR-14 | Final Result chỉ được tạo sau Final Validation trên phiên bản dữ liệu hiện hành |
| BR-15 | Preference Memory phải ẩn danh; không dùng phản hồi để sửa Ontology hoặc hard constraints |
| BR-16 | Khi candidate hoặc snapshot thay đổi, vô hiệu hóa và thực hiện lại Validation, Ranking, Explanation phụ thuộc |
| BR-17 | Feedback tạo preference hoặc Adjustment Request, không sửa trực tiếp kế hoạch hay knowledge snapshot |

## 9. Kết quả đầu ra

Mỗi phương án gồm loại/mục tiêu, danh sách và phân loại môn, tổng tín chỉ, điểm, lý do chọn/loại, cảnh báo, trạng thái Validation và evidence. Kết quả Validation gồm valid/invalid, violations, warnings, evidence và phiên bản nguồn.

## 10. Yêu cầu phản hồi và lập lại kế hoạch

- Cho phép chọn/xếp hạng A/B/C.
- Cho phép Add, Remove, Replace, Change Target Credits hoặc Change Goal.
- Giải thích khi điều chỉnh vi phạm.
- Không bỏ kiểm tra vì phản hồi.
- Mỗi vòng tạo phiên bản mới.
- Giới hạn số vòng và báo khi hết phương án.
- Lưu Preference Dataset gồm student_id_anonymous, planning_request_id, plan_a_features, plan_b_features, selected_plan, advisor_feedback và timestamp.
- Tạo cặp ưu tiên từ hai phương án hợp lệ và dùng vector đặc trưng để học hàm xếp hạng LTR.
- Trong thực nghiệm, preference của cố vấn là tín hiệu giám sát chính; phản hồi sinh viên được lưu để phân tích hoặc mở rộng.
- LTR chỉ học thứ tự của phương án đã qua Validator.

## 11. Trường hợp ngoại lệ

| Trường hợp | Xử lý |
|---|---|
| Lỗi hoặc thiếu dữ liệu | Orchestrator dừng nhánh xử lý; ghi lỗi vào Evidence/Trace |
| Hết không gian tìm kiếm | Dừng và giải thích nguyên nhân |
| Không đủ điều kiện học vượt | Không tạo và giải thích |
| Không đủ ba phương án | Hiển thị phương án hợp lệ hiện có |
| Điều chỉnh vi phạm | Từ chối kèm giải thích |
| Dữ liệu thay đổi | Vô hiệu hóa kết quả phụ thuộc và kiểm tra lại trên phiên bản phù hợp |
| Ontology/Rule Engine lỗi | Không hiển thị kế hoạch chưa kiểm chứng |
| Vượt giới hạn lập lại | Dừng; giữ iteration/version và trace các vòng trước |

## 12. Phạm vi và đánh giá nghiên cứu

Ba đóng góp dự kiến là Ontology-constrained AI Agent, Grounded Explanation dựa trên Ontology Evidence và Human-in-the-loop Preference Learning.

- LangGraph/Pydantic dự kiến cho MVP; LTR, pgvector/RAG và LLM là phần mở rộng theo PDF.
- So sánh BL-01 Rule-based, BL-02 Greedy, BL-03 Beam Search hiện tại, BL-04 Agent không Ontology chỉ chạy offline, BL-05 Agent có Ontology và BL-06 Agent có Ontology + Preference Learning/LTR.
- BL-04 không dùng tri thức quan hệ/ràng buộc Ontology hoặc phản hồi Ontology Validator trong generation; đầu ra được hậu kiểm bằng cùng Standard Validator như các baseline khác.
- So sánh EX-ABL-01 không explanation và EX-ABL-02 có grounded explanation, giữ nguyên candidate plans, Validation và Ranking.
- Chia train/validation/test theo student_id; đóng băng dữ liệu và tham số trước đánh giá cuối. Các baseline có cùng đầu vào và ngân sách thực nghiệm, theo phạm vi tri thức của từng baseline.
- Đánh giá tính hợp lệ, đồng thuận cố vấn, NDCG@3/MRR, mức chỉnh sửa, độ đa dạng, chất lượng explanation và hiệu năng.
- Giải thích được đánh giá qua groundedness, evidence coverage và đánh giá cố vấn về clarity, usefulness, trust, acceptance.

Công thức và protocol chi tiết nằm trong mục 7–8 của [tài liệu thiết kế](THIET_KE_AI_AGENT.md).
