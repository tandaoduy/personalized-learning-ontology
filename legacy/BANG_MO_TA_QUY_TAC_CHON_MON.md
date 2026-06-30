# Bảng mô tả quy tắc chọn môn & Beam Search (chi tiết)

Tài liệu này mô tả logic của script CLI legacy `legacy/recommend_source.py`. Luồng web Flask hiện tại dùng `RecommendationEngine` và API JSON, không phụ thuộc TXT làm đầu ra chính.

---

## 1) Tổng quan pipeline

| Bước | Mục tiêu | Đầu vào chính | Đầu ra |
|---|---|---|---|
| 1. Nạp dữ liệu | Đọc hồ sơ SV + ontology môn học | `data/DanhSachSinhVien.json`, `owl/current/ontology_v19.rdf` | `target_student`, `course_data` |
| 2. Chuẩn hóa trạng thái học | Xác định môn đã đạt/chưa đạt | `điểm từng môn`, `danh sách môn đã học`, `danh sách môn chưa đạt` | `passed_courses`, `failed_courses` |
| 3. Lọc môn đủ điều kiện | Giữ môn có thể đăng ký | tiên quyết, kỳ mở, kỳ khuyến nghị, chuyên ngành, ràng buộc cứng | `valid_courses` |
| 4. Gắn điểm heuristic | Chấm điểm ưu tiên từng môn | debt, phụ thuộc, trễ kỳ, kỳ mở, mục tiêu học | `điểm ưu tiên`, `điểm tổng ưu tiên` |
| 5. Phân nhóm tự chọn | Nhóm theo đại cương/thể chất/cơ sở ngành/chuyên ngành | type môn trong ontology | các list nhóm môn |
| 6. Tính quota còn thiếu | Chỉ gợi ý phần tự chọn chưa hoàn thành | quota mục tiêu - số đã hoàn thành | `remaining_elective_counts` |
| 7. Random ứng viên cho tổ hợp cuối | Random chỉ ở giai đoạn tổ hợp cuối | pool môn tự chọn hợp lệ | `beam_candidates` |
| 8. Beam Search | Chọn tổ hợp cuối không vượt tín chỉ | `beam_candidates`, quota, score | `valid_courses` (tổ hợp cuối) |
| 9. Xuất kết quả | Terminal + TXT cho script CLI legacy | `eligible_courses`, `valid_courses` | báo cáo terminal và TXT |

---

## 2) Thuộc tính môn học trích từ ontology

| Thuộc tính | Nguồn | Ý nghĩa trong thuật toán |
|---|---|---|
| `courseCode`, `courseName` | ontology | Mã/tên môn |
| `hasPrerequisiteCourse` | ontology | Tiên quyết |
| `openSemesterType` | ontology | Kỳ mở môn: 1 (lẻ), 2 (chẵn), 3/12 (cả hai) |
| `recommendedInSemester` | ontology | Kỳ khuyến nghị |
| `isRequiredForMajor/Specialization` | ontology | Môn bắt buộc |
| `isElectiveForMajor/Specialization` | ontology | Môn tự chọn |
| `GeneralEducationCourse` | type | Nhóm tự chọn đại cương |
| `PhysicalEducationCourse` | type | Nhóm tự chọn thể chất |
| `FoundationCourse` | type | Nhóm tự chọn cơ sở ngành |
| còn lại (elective specialization) | suy luận | Nhóm tự chọn chuyên ngành |
| `corequisiteWith` | ontology | Môn song hành (bundle khi chọn) |

---

## 3) Quy tắc lọc môn đủ điều kiện (đầu vào)

Một môn được vào **tập môn hợp lệ** khi thỏa đồng thời:

| Điều kiện | Mô tả |
|---|---|
| Chưa đạt | Môn không nằm trong `passed_courses` |
| Tiên quyết đạt | Mọi môn tiên quyết đều trong `passed_courses`; nếu tiên quyết rớt hoặc thiếu thì loại |
| Mở đúng kỳ | `openSemesterType` khớp kỳ đăng ký (`next_sem`) hoặc là mở cả 2 kỳ |
| Kỳ khuyến nghị | `học vượt`: cho phép vượt kỳ khuyến nghị; mục tiêu khác: chỉ nhận môn có `recommended_sem <= next_sem` |
| Chuyên ngành khớp | Nếu SV đã chọn chuyên ngành, môn thuộc chuyên ngành đó hoặc không gắn chuyên ngành; nếu chưa chọn chuyên ngành thì chỉ nhận môn phù hợp rule hiện tại |
| Không quá tải bất thường | Tín chỉ môn không vượt `REGISTER_MAX_CREDITS` |
| Ràng buộc cứng nghiệp vụ | (1) Môn khuyến nghị kỳ 8 chỉ gợi ý ở kỳ 8; (2) Môn thực tập ngành (`INT6900`, `SOT348`, hoặc tên chứa “thực tập ngành”) chỉ gợi ý ở kỳ 7 |

> Ghi chú: `passed_courses` được hợp nhất từ cả `điểm từng môn` + `danh sách môn đã học`, rồi trừ `danh sách môn chưa đạt`.

---

## 4) Công thức heuristic & điểm tổng

### 4.1 Điểm heuristic cơ sở

\[
H = debt \times 1000 + doPhu \times 20 + doTre \times 50
\]

Trong đó:
- `debt`: 1 nếu là môn học lại, ngược lại 0.
- `doPhu`: số môn khác phụ thuộc vào môn này (đếm từ quan hệ tiên quyết toàn cục).
- `doTre`: `max(0, current_sem - recommended_sem)`.

### 4.2 Điểm tổng ưu tiên

\[
H_{total} = H + openNow \times 50 + recProximity \times 10 + goalScore
\]

Với:
- `openNow`: 1 nếu môn mở đúng kỳ đang đăng ký, ngược lại 0.
- `recProximity = max(0, 10 - |next_sem - recommended_sem|)`.
- `goalScore` theo mục tiêu học tập:

| Mục tiêu | goalScore |
|---|---:|
| Đúng hạn | 30 |
| Giảm tải | 20 |
| Học vượt | 10 |
| Khác/không có | 0 |

---

## 5) Quy tắc quota tự chọn

### 5.1 Quota mục tiêu

| Nhóm tự chọn | Quota mục tiêu |
|---|---:|
| Đại cương (`general`) | 1 |
| Thể chất (`physical`) | 2 |
| Cơ sở ngành (`foundation`) | 1 |
| Chuyên ngành (`specialization`) | 3 |

> `Học vượt` hiện vẫn để chuyên ngành = 3.

### 5.2 Quota còn thiếu

\[
remaining[group] = max(0, target[group] - completed[group])
\]

`completed[group]` được đếm trên các môn đã đạt (`passed_courses`) theo nhóm tự chọn.

### 5.3 Rule đặc biệt theo mục tiêu

| Mục tiêu | Rule tổ hợp cuối |
|---|---|
| Đúng hạn / Giảm tải | Tối đa 1 môn tự chọn trong tổ hợp cuối |
| Học vượt | Không bị chặn 1 môn tự chọn; chọn theo quota còn thiếu và tín chỉ |

---

## 6) Randomization (đúng nơi áp dụng)

### 6.1 Không random ở “Tập môn hợp lệ”
- `eligible_courses` luôn in **đầy đủ** các môn hợp lệ sau lọc.

### 6.2 Random ở “Tổ hợp cuối cùng”
- Tạo `beam_candidates` từ `eligible_courses`, rồi random theo rule:

| Trường hợp | Cách random |
|---|---|
| Đúng hạn/Giảm tải (chỉ 1 tự chọn) | Nếu có tự chọn chuyên ngành thì random trong pool chuyên ngành trước; nếu không có thì random trong toàn bộ pool tự chọn |
| Học vượt / mode khác | Với mỗi nhóm có `remain > 0`, nếu pool lớn hơn `remain` thì `random.sample(pool, remain)` |
| Trong beam | `random.shuffle(beam_candidates)`, `random.shuffle(remaining)` và `tie_break = random.random()` để phá hòa |

---

## 7) Beam Search chi tiết

## 7.1 State

Mỗi state gồm:
- `selected_codes`: set mã môn đã chọn.
- `selected_courses`: danh sách môn đã chọn.
- `credit`: tổng tín chỉ.
- `score`: tổng `H_total`.
- `elective_counts`: số môn tự chọn theo từng nhóm.
- `tie_break`: số ngẫu nhiên để phá hòa.

## 7.2 Mở rộng state

Cho mỗi môn chưa chọn:
1. Resolve bundle song hành (`corequisite`) bằng DFS stack.
2. Tính `bundle_credit`, `next_elective_counts`.
3. Loại nếu vượt `student_max_credit`.
4. Loại nếu vi phạm quota tự chọn (`within_elective_quota`).
5. Tạo state mới với score cộng dồn từ các môn trong bundle.

## 7.3 Cắt tỉa beam

- `beam_width = 8`.
- Sau mỗi vòng mở rộng:
  - Gộp state mới + state cũ.
  - Sort giảm dần theo:

\[
(quotaFillScore,
score,
credit,
tie\_break)
\]

- Giữ top 8 state.

### Hàm `quotaFillScore`
- Nếu `đúng hạn/giảm tải`: chỉ tính tối đa 1 tự chọn.
- Ngược lại: tổng `min(count[group], remaining[group])` qua 4 nhóm.

## 7.4 Chọn `best_state`
- Ưu tiên state có `quotaFillScore` cao hơn.
- Nếu hòa: ưu tiên `score` cao hơn.
- Nếu còn hòa: ưu tiên `credit` cao hơn.
- Cuối cùng nhờ `tie_break` giảm tính cố định.

---

## 8) Xuất kết quả

| Kênh | Nội dung |
|---|---|
| Terminal | Tóm tắt + danh sách môn cuối + lý do từng môn |
| TXT report | Đầy đủ 3 phần: tập môn hợp lệ, tổ hợp cuối, giải thích thuật toán |

---

## 9) Thứ tự ưu tiên ràng buộc (quan trọng)

1. Ràng buộc cứng học vụ (kỳ 8, thực tập ngành kỳ 7).
2. Tiên quyết + kỳ mở + chuyên ngành + trần tín chỉ.
3. Quota còn thiếu theo nhóm tự chọn.
4. Rule theo mục tiêu học tập (đúng hạn/giảm tải chỉ 1 tự chọn ở tổ hợp cuối).
5. Heuristic và beam ranking để chọn phương án tối ưu.

---

## 10) Ví dụ diễn giải nhanh cho 1 môn

Giả sử môn X có:
- `debt=0`, `doPhu=2`, `doTre=1`, mở đúng kỳ, cách kỳ khuyến nghị 0,
- mục tiêu `đúng hạn`.

Khi đó:
- \(H = 0*1000 + 2*20 + 1*50 = 90\)
- \(H_{total} = 90 + 1*50 + 10*10 + 30 = 270\)

Môn được xếp hạng cao hơn các môn có `H_total` thấp hơn, miễn không vi phạm quota/credit/ràng buộc cứng.

---

## 11) Gợi ý vận hành

- Nếu muốn kết quả reproducible (tái lập được), thêm `random.seed(...)` theo mã SV + học kỳ.
- Nếu muốn giảm biến động, chỉ random ở bước tie-break thay vì random pool trước beam.
- Nếu muốn kiểm soát chính sách dễ hơn, đưa các quota/ràng buộc vào file config JSON.
