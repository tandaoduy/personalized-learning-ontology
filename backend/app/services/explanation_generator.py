"""
Tạo giải thích cho quyết định gợi ý môn học
"""

from typing import List, Dict
from backend.app.models.recommendation import RecommendationResult


class ExplanationGenerator:
    """Tạo giải thích lý do tại sao môn được chọn"""
    
    def generate_beam_search_explanation(self, 
                                         beam_width: int,
                                         iterations: int,
                                         final_quota_fill: int,
                                         total_quota_categories: int = 4) -> str:
        """Giải thích chi tiết thuật toán tìm kiếm chùm"""
        
        explanation = f"""
=== GIẢI THÍCH THUẬT TOÁN TÌM KIẾM CHÙM ===

1. TỔNG QUAN:
   - Độ rộng chùm: {beam_width} (giữ {beam_width} trạng thái tốt nhất mỗi vòng)
   - Mục tiêu: Tìm tổ hợp môn tối ưu trong ràng buộc (tín chỉ, hạn ngạch, điểm)
   - Kết quả: Đạt {final_quota_fill}/{total_quota_categories} hạn ngạch danh mục tự chọn

2. LUỒNG THUẬT TOÁN:
   Vòng lặp (đến khi hội tụ):
     - Với mỗi trạng thái hiện tại:
       • Lấy tất cả môn chưa chọn
       • Thử thêm từng môn (hoặc gộp môn song hành)
       • Kiểm tra: tín chỉ ≤ tối đa ✓, hạn ngạch OK ✓, tiên quyết ✓?
       → Nếu OK, tạo trạng thái mới: trạng thái_mới = trạng thái + môn
       
     - Giữ lại TOP {beam_width} trạng thái theo:
       1. Đáp ứng hạn ngạch tự chọn cao nhất
       2. Điểm ưu tiên cao nhất (nếu hòa)
       3. Tín chỉ nhiều nhất (nếu hòa)
   
   Kết thúc khi không có trạng thái mới hoặc đã lặp đủ lần

3. CHỌN KẾT QUẢ:
   - Trạng thái tốt nhất = trạng thái có (đáp ứng hạn ngạch, điểm ưu tiên, tín chỉ) cao nhất
   - Đảm bảo:
     ✓ Tổng tín chỉ không vượt giới hạn cấu hình đăng ký
     ✓ Hạn ngạch tự chọn phù hợp
     ✓ Tất cả tiên quyết được thỏa

4. ĐẶC ĐIỂM:
   - Tư duy: Tìm gần tối ưu thay vì vét cạn
   - Thời gian: O(beam_width × num_courses) (đa thức)
   - So sánh: Vét cạn sẽ là O(2^num_courses) (mũ, không khả thi)
"""
        return explanation
    
    def generate_heuristic_explanation(self) -> str:
        """Giải thích công thức chấm điểm"""
        
        explanation = """
=== GIẢI THÍCH CÔNG THỨC CHẤM ĐIỂM ===

Công thức Điểm Ưu Tiên:

H = debt × 1000 + doPhu × 20 + doTre × 50

  ┌─────────────────────────────────────────────────┐
  │ debt (Nợ Môn): 1 nếu bị trượt, 0 nếu chưa học   │
  │ → Trọng số 1000 (cao nhất!)                     │
  │ → Ưu tiên: PHẢI học lại môn nợ trước           │
  │ → VD: SV0016 trượt INS330 → debt=1 → +1000      │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │ doPhu (Số Môn Phụ Thuộc):                       │
  │ = số môn khác có tiên quyết là môn này          │
  │ → Trọng số 20                                    │
  │ → Ưu tiên: Học môn có nhiều "con em"          │
  │ → VD: SOT320 có 3 môn phụ thuộc → doPhu=3      │
  │      → +60 điểm                                 │
  │ → Logic: Mở khóa nhiều cơ hội học tiếp         │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │ doTre (Trễ Kỳ):                                 │
  │ = max(0, current_semester - recommended_sem)   │
  │ → Trọng số 50                                    │
  │ → Ưu tiên: Môn bị trễ so với lộ trình          │
  │ → VD: MAT327 khuyến nghị S3, SV ở S5:          │
  │      doTre = 5-3 = 2 → +100 điểm               │
  │ → Logic: Tránh tình trạng quá trễ lộ trình    │
  └─────────────────────────────────────────────────┘

H_total = H + openNow × 50 + recProximity × 10 + goalScore

  ┌─────────────────────────────────────────────────┐
  │ openNow: 1 nếu mở đúng kỳ đang đăng ký, 0      │
  │ → Trọng số 50                                    │
  │ → Logic: Môn mở sẵn là tốt, không cần chờ     │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │ recProximity: max(0, 10 - |next_sem - rec_sem|)│
  │ → Nếu next_sem = 4, rec_sem = 3: gap=1         │
  │    → recProximity = 10-1 = 9 → +90 điểm         │
  │ → Nếu next_sem = 8, rec_sem = 3: gap=5         │
  │    → recProximity = 10-5 = 5 → +50 điểm         │
  │ → Logic: Gần khuyến nghị → ưu tiên              │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │ goalScore: Phụ thuộc mục tiêu học               │
  │ = 30 nếu "đúng hạn"                             │

  │ = 10 nếu "học vượt"                             │
  │ → Logic: Ưu tiên môn phù hợp chiến lược SV     │
  └─────────────────────────────────────────────────┘

VÍ DỤ THỰC TẾ:
─────────────

Học viên: SV0016, ở kỳ 3, mục tiêu "đúng hạn"

Môn A: INS330 (Cơ sở dữ liệu)
  - debt = 1 (trượt ở kỳ 1)
  - doPhu = 2 (SOT341, SOT342 cần INS330)
  - doTre = 3 - 2 = 1 (khuyến nghị kỳ 2, giờ kỳ 3)
  - H = 1×1000 + 2×20 + 1×50 = 1090
  
  - openNow = 1 (mở kỳ lẻ, kỳ 3 lẻ)
  - recProximity = max(0, 10 - |3-2|) = 9
  - goalScore = 30 (mục tiêu đúng hạn)
  - H_total = 1090 + 50 + 90 + 30 = 1260
  
  → ĐIỂM CAO → ƯU TIÊN ĐƯỢC CHỌN TRƯỚC

Môn B: SOT350 (Tự chọn)
  - debt = 0 (chưa học)
  - doPhu = 0 (không có môn phụ thuộc)
  - doTre = 0 (khuyến nghị kỳ 4, hiện kỳ 3)
  - H = 0 + 0 + 0 = 0
  
  - openNow = 1
  - recProximity = max(0, 10 - |3-4|) = 9
  - goalScore = 30
  - H_total = 0 + 50 + 90 + 30 = 170
  
  → ĐIỂM THẤP → CHỌN SAU (CÓ THỂ KHÔNG ĐƯỢC CHỌN)
"""
        return explanation
    
    def generate_recommendation_summary(self, result: RecommendationResult, max_credits: int) -> str:
        """Tóm tắt kết quả gợi ý.

        `max_credits` được truyền từ cấu hình để tránh hardcode giới hạn tín chỉ.
        """
        sections = [
            self._build_summary_header(result),
            self._build_summary_result(result, max_credits),
            self._build_quota_section(result),
        ]

        if result.warnings:
            sections.append(self._build_warning_section(result.warnings))

        return "\n\n".join(section for section in sections if section).strip()

    def _build_summary_header(self, result: RecommendationResult) -> str:
        return f"""=== TÓM TẮT KẾ HOẠCH HỌC TẬP ===

Sinh viên: {result.student_name} ({result.student_id})
Học kỳ hiện tại: {result.current_semester} → Đăng ký kỳ: {result.next_semester}
Mục tiêu học: {result.study_goal}"""

    def _build_summary_result(self, result: RecommendationResult, max_credits: int) -> str:
        lines = [
            "KẾT QUẢ:",
            "─────────",
            "",
            "Danh sách môn hợp lệ (đầu vào tìm kiếm chùm):",
            f"  • Tổng số: {result.total_eligible_count} môn",
            "  • Gồm: môn bắt buộc, tự chọn, học lại",
            "  • Những môn này đã thỏa 8 điều kiện kinh doanh:",
            "    ✓ Chưa đạt",
            "    ✓ Tiên quyết OK",
            "    ✓ Kỳ mở phù hợp",
            "    ✓ Kỳ khuyến nghị phù hợp mục tiêu",
            "    ✓ Chuyên ngành khớp",
            "    ✓ Tín chỉ không quá tải",
            "    ✓ Không vi phạm ràng buộc cứng kỳ 8 vs kỳ 7",
            "    + Hạn ngạch tự chọn chưa đầy",
            "",
            "Tổ hợp đề xuất (kết quả tìm kiếm chùm):",
            f"  • Tổng số: {result.total_recommended_count} môn",
            f"  • Tổng tín chỉ: {result.total_recommended_credits}/{max_credits}",
            "  • Danh sách:",
        ]

        for i, course in enumerate(result.recommended_courses, 1):
            status = "Học lại" if course.is_retake else f"S{course.recommended_semester}"
            lines.extend([
                "",
                f"    {i}. {course.code} - {course.name}",
                f"       TC: {course.credits} | {status} | Điểm: {course.total_priority_score:.0f}",
                f"       Lý do: {', '.join(course.reasons)}",
            ])

        return "\n".join(lines)

    def _build_quota_section(self, result: RecommendationResult) -> str:
        lines = [
            "TIẾN ĐỘ HẠN NGẠCH MÔN TỰ CHỌN:",
            "─────────────────────",
            "",
            "Danh mục           | Đã Hoàn | Mục Tiêu | Còn Thiếu | Đã Chọn",
            "─────────────────────────────────────────────────────────",
        ]

        for cat in ['general', 'physical', 'foundation', 'specialization']:
            completed = result.elective_completed_counts.get(cat, 0)
            target = result.elective_target_quotas.get(cat, 0)
            remaining = result.elective_quota_remaining.get(cat, 0)
            finalized = result.finalized_elective_counts.get(cat, 0)

            cat_name = {
                'general': 'Đại cương',
                'physical': 'Thể chất',
                'foundation': 'Cơ sở ngành',
                'specialization': 'Chuyên ngành',
            }.get(cat, cat)

            lines.append(f"{cat_name:15} | {completed:7} | {target:8} | {remaining:9} | {finalized:8}")

        return "\n".join(lines)

    def _build_warning_section(self, warnings: List[str]) -> str:
        lines = [
            "CẢNH BÁO:",
            "─────────",
        ]
        for warning in warnings:
            lines.append(f"  ⚠ {warning}")
        return "\n".join(lines)
