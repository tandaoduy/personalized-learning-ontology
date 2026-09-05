# Cấu trúc bộ máy gợi ý phục vụ MVP

Điểm gọi công khai vẫn là `backend.app.services.recommendation_engine.RecommendationEngine`. Flask routes, benchmark và tests tiếp tục dùng điểm gọi này.

| Module | Trách nhiệm được tách từ engine |
|---|---|
| `ontology.py` | Nạp RDF, phân loại môn tự chọn, chuỗi tiên quyết và đường phụ thuộc |
| `eligibility.py` | Chuẩn hóa lịch sử học, lọc môn và quota; hiện vẫn chứa scoring theo môn |
| `candidate_generation.py` | Chuẩn bị ứng viên và Beam Search hiện tại |
| `plan_risk.py` | Ước lượng độ khó, tải học, cảnh báo và điểm rủi ro |
| `constants.py` | URI RDF, trọng số và ngoại lệ dữ liệu hiện có |
| `../recommendation_engine.py` | Khởi tạo context, phối hợp các bước và giữ API tương thích |

Các lớp `*Mixin` là bước tách nội bộ: chúng cùng dùng context của engine như `course_data`, `graph`, giới hạn tín chỉ và trọng số. Không khởi tạo chúng như service độc lập. Cách này giữ nguyên thân hàm, lời gọi nội bộ và cách cấu hình engine trong giai đoạn chuyển đổi.

Chưa xem các module này là Agent capabilities hoàn chỉnh: chưa có hợp đồng schema, provenance và version snapshot. Logic lọc trong Eligibility/Beam Search cũng chưa thay thế Standard Validator độc lập.

Hướng phát triển tiếp theo là xây dựng schema và context tường minh, sau đó đóng gói từng capability. Standard Validator sẽ nhận plan cùng snapshot và kiểm tra độc lập, không gọi Generator để kết luận validity. Agent Orchestrator sẽ gọi các capability; các module nghiệp vụ không được import ngược Agent hoặc Flask routes.

Không chuyển ontology, dữ liệu hoặc templates/static trong đợt này. Không đổi thuật toán, seed, trọng số hoặc cách chọn phương án. Các ngoại lệ trong `constants.py` là quy tắc/điều chỉnh hiện có trong code, không mặc nhiên là bằng chứng lấy từ ontology.
