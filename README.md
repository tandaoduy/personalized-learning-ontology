# Đề tài gợi ý kế hoạch học tập dựa trên Ontology

Tài liệu này là nguồn mô tả chính của project. Phần kiến trúc và hướng dẫn triển khai đã được gộp vào đây để tránh trùng lặp.


## 1) Mục tiêu đề tài

Xây dựng hệ thống hỗ trợ sinh viên đăng ký môn học theo học kỳ bằng cách kết hợp:

- Dữ liệu hồ sơ học tập sinh viên
- Ontology chương trình đào tạo
- Tập luật học vụ
- Chấm điểm heuristic và tìm kiếm chùm (Beam Search) để tối ưu tổ hợp môn

Hệ thống trả về:

- Tập môn hợp lệ có thể đăng ký
- Tổ hợp môn đề xuất cuối cùng
- Giải thích lý do chọn môn để người đọc hiểu rõ quyết định của thuật toán

---

## 2) Cấu trúc thư mục tổng thể (root)

```text
Code/
├─ owl/
│  ├─ current/
│  │  ├─ ontology_v19.rdf
│  │  ├─ ontology_v19.properties
│  │  └─ TrainingProgramOntology_v19.owl
│  └─ archive/
│     └─ ... (các version ontology cũ hơn)
│
├─ data/
│  ├─ DanhSachSinhVien.json
│  └─ DanhSachSinhVien.csv
│
├─ legacy/
│  ├─ recommend_source.py
│  ├─ test_sparql.py
│  ├─ BANG_MO_TA_QUY_TAC_CHON_MON.md
│  └─ outputs/
│     └─ Output_TestSPARQL.txt
│
└─ README.md
```

Các thành phần quan trọng:

- Ontology chính đang dùng: [owl/current/ontology_v19.rdf](owl/current/ontology_v19.rdf)
- Bộ máy gợi ý đang chạy trong web app: [flask_app/services/recommendation_engine.py](flask_app/services/recommendation_engine.py)
- Script CLI cũ chỉ còn giữ lại để tham khảo/offline: [legacy/recommend_source.py](legacy/recommend_source.py)
- Script kiểm tra SPARQL: [legacy/test_sparql.py](legacy/test_sparql.py)
- Dữ liệu sinh viên JSON: [data/DanhSachSinhVien.json](data/DanhSachSinhVien.json)
- Dữ liệu sinh viên CSV (fallback): [data/DanhSachSinhVien.csv](data/DanhSachSinhVien.csv)
- Mô tả quy tắc chi tiết hiện hành: [legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md](legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md)

---

## 3) Vai trò của Ontology trong hệ thống

Ontology là nguồn tri thức học vụ chuẩn để thuật toán suy luận điều kiện đăng ký môn.

### 3.1 Dữ liệu ontology cung cấp

Từ ontology, hệ thống trích xuất cho mỗi môn:

- Mã môn học, tên môn học
- Quan hệ tiên quyết
- Quan hệ song hành
- Học kỳ mở môn (lẻ, chẵn, cả hai)
- Học kỳ khuyến nghị
- Thuộc tính bắt buộc/tự chọn theo ngành hoặc chuyên ngành
- Loại môn (đại cương, thể chất, cơ sở ngành)
- Số tín chỉ

### 3.2 Ý nghĩa

Nhờ ontology, hệ thống không chỉ lọc theo dữ liệu điểm mà còn kiểm tra logic chương trình đào tạo theo ngữ nghĩa học vụ.

---

## 4) Luồng xử lý tổng thể (end-to-end)

### Bước 1: Nhận đầu vào

Luồng web chính hiện tại nhận request qua Flask API:

- `POST /api/recommendations` với `student_id`
- Hồ sơ sinh viên được đọc từ `StudentDataService`
- Ontology được nạp sẵn trong `RecommendationEngine`
- CSV chỉ là nguồn dự phòng khi JSON chưa có dữ liệu

Nếu không tìm thấy sinh viên trong JSON, hệ thống mới dùng CSV fallback để đảm bảo demo vẫn chạy.

### Bước 2: Nạp ontology và dựng dữ liệu môn học

Từ [owl/current/ontology_v19.rdf](owl/current/ontology_v19.rdf), hệ thống dựng course_data gồm:

- Prerequisite, corequisite
- Kỳ mở, kỳ khuyến nghị
- Gắn chuyên ngành/nhóm môn
- Tín chỉ và phân loại bắt buộc/tự chọn

### Bước 3: Chuẩn hóa hồ sơ sinh viên

Từ hồ sơ sinh viên, hệ thống tạo:

- passed_courses: môn đã đạt
- failed_courses: môn chưa đạt

Điểm quan trọng:

- Hợp nhất nguồn môn đã học từ điểm từng môn + danh sách môn đã học
- Loại bỏ giao nhau với danh sách môn chưa đạt
- Chuẩn hóa mã môn để tăng tính nhất quán
- Cảnh báo các mã môn không tồn tại trong ontology

### Bước 4: Lọc tập môn hợp lệ

Mỗi môn chỉ được giữ lại nếu thỏa đồng thời:

- Chưa đạt
- Đủ điều kiện tiên quyết
- Mở đúng loại học kỳ
- Phù hợp kỳ khuyến nghị theo mục tiêu học tập
- Phù hợp chuyên ngành đã chọn
- Thỏa ràng buộc cứng (ví dụ môn thực tập ngành, môn khuyến nghị kỳ 8)

### Bước 5: Chấm điểm ưu tiên

Hệ thống chấm mỗi môn theo:

- Debt score: ưu tiên môn học lại
- Link score: ưu tiên môn có nhiều môn phụ thuộc
- Delay score: ưu tiên môn bị trễ so với kế hoạch
- Open semester score
- Recommended semester proximity score
- Goal score theo mục tiêu học tập

Sau đó tính điểm tổng ưu tiên để xếp hạng.

### Bước 6: Quota tự chọn

Phân nhóm tự chọn:

- Đại cương
- Thể chất
- Cơ sở ngành
- Chuyên ngành

Tính số đã hoàn thành và quota còn thiếu để chỉ giữ môn tự chọn còn cần thiết.

### Bước 7: Tìm kiếm chùm (Beam Search) tối ưu tổ hợp môn

Sử dụng tìm kiếm chùm (Beam Search) để chọn tổ hợp cuối cùng với ràng buộc:

- Không vượt giới hạn tín chỉ
- Tôn trọng quota tự chọn
- Tôn trọng bundle môn song hành
- Ưu tiên state có độ đáp ứng quota + điểm tổng + tín chỉ tốt hơn

### Bước 8: Xuất kết quả

Hệ thống xuất:

- Kết quả tóm tắt ra terminal chỉ dùng để debug/đối chiếu khi chạy script legacy
- Báo cáo chi tiết ra file txt chỉ còn là đầu ra của script CLI cũ trong `legacy`

Các file báo cáo mẫu: [legacy](legacy)

---

## 5) Mô tả các module chính

### 5.1 Module gợi ý môn

- File đang chạy trong web app: [flask_app/services/recommendation_engine.py](flask_app/services/recommendation_engine.py)
- File CLI cũ chỉ còn để tham khảo: [legacy/recommend_source.py](legacy/recommend_source.py)
- Nhiệm vụ:
  - Nạp dữ liệu sinh viên + ontology
  - Lọc môn hợp lệ
  - Chấm điểm heuristic
  - Chạy beam search
  - Xuất kết quả JSON cho Flask

### 5.2 Module kiểm thử SPARQL

- File: [legacy/test_sparql.py](legacy/test_sparql.py)
- Nhiệm vụ:
  - Chạy các truy vấn SPARQL kiểm tra dữ liệu ontology
  - Kiểm tra môn theo học kỳ, tiên quyết, song hành, nhóm chuyên ngành
  - Hỗ trợ xác minh ontology đúng logic trước khi recommendation

### 5.3 Tài liệu quy tắc nghiệp vụ

- File: [legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md](legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md)
- Nhiệm vụ:
  - Mô tả đầy đủ quy tắc lọc, scoring, quota, beam search
  - Là tài liệu đối chiếu với code

---

## 6) Quy ước dữ liệu đầu vào

### 6.1 Hồ sơ sinh viên

Nguồn chính: [data/DanhSachSinhVien.json](data/DanhSachSinhVien.json)

Các trường thường dùng:

- mã sinh viên
- tên sinh viên
- học kỳ hiện tại
- chuyên ngành chọn
- mục tiêu học tập
- điểm từng môn
- danh sách môn đã học
- danh sách môn chưa đạt
- số tín chỉ đăng ký tối đa

### 6.2 Chuẩn hóa đầu vào

Hệ thống có xử lý chuẩn hóa để chống sai khác dữ liệu:

- Mã sinh viên: so khớp linh hoạt
- Mã môn: chuẩn hóa kiểu chữ
- Mục tiêu học tập: map về nhóm chuẩn
- Số học kỳ và tín chỉ: ép kiểu an toàn

---

## 7) Cách chạy hệ thống

Chạy web app Flask từ root workspace:

```bash
python run_app.py
```

Sau đó mở:

- `http://localhost:5000/`
- `http://localhost:5000/students`
- `http://localhost:5000/api/health`

Nếu cần chạy script CLI legacy để đối chiếu offline:

```bash
python legacy/recommend_source.py --student-id SV0016
```

Chạy kiểm tra SPARQL:

```bash
python legacy/test_sparql.py --ontology owl/current/ontology_v19.rdf
```

---

## 8) Đầu ra và cách đọc kết quả

### 8.1 Terminal

Hiển thị:

- Thông tin sinh viên
- Số môn hợp lệ
- Danh sách môn đề xuất cuối cùng
- Lý do chọn từng môn

### 8.2 Báo cáo txt (legacy)

File TXT chỉ còn là đầu ra của script CLI cũ trong [legacy/recommend_source.py](legacy/recommend_source.py).  
Trong web app Flask hiện tại, đầu ra chính là JSON API và giao diện HTML.

Nếu vẫn chạy script legacy này, file report có timestamp sẽ nằm trong thư mục [legacy](legacy), gồm:

- Tập môn hợp lệ đầu vào
- Tổ hợp môn cuối cùng
- Mô tả logic beam search đã áp dụng

---

## 9) Nguyên tắc thiết kế hiện tại

- Chặt chẽ nghiệp vụ: ưu tiên ràng buộc học vụ trước tối ưu điểm
- Giải thích được: mọi môn có lý do đi kèm
- Dễ tái lập: random có kiểm soát để tránh dao động vô nghĩa
- Tách nguồn tri thức: ontology tách khỏi code thuật toán


## 10) Định hướng mở rộng

- Đưa quota/ràng buộc thành file cấu hình riêng để thay đổi không cần sửa code
- Bổ sung test tự động cho các case biên (học lại, chuyên ngành, corequisite, quota)
- Xây API hoặc giao diện web để nhập mã sinh viên và xem gợi ý trực quan
- Thêm giải thích sâu ở mức rule-by-rule cho từng môn bị loại

---

## 11) Tài liệu liên quan trong repo

- [README.md](README.md)
- [owl](owl)
- [legacy/recommend_source.py](legacy/recommend_source.py)
- [legacy/test_sparql.py](legacy/test_sparql.py)
- [legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md](legacy/BANG_MO_TA_QUY_TAC_CHON_MON.md)
- [legacy/outputs/Output_TestSPARQL.txt](legacy/outputs/Output_TestSPARQL.txt)
