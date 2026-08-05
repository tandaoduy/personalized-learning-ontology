"""
Các model dữ liệu cho kết quả gợi ý
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class RecommendedCourse:
    """Một môn học được đề xuất"""
    
    code: str
    name: str
    credits: int
    is_retake: bool = False
    recommended_semester: int = 0
    heuristic_score: float = 0.0
    total_priority_score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    corequisites: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ExcludedCourse:
    """Một môn học bị loại khỏi luồng gợi ý cùng lý do rule-by-rule."""

    code: str
    name: str
    credits: int = 0
    recommended_semester: int = 0
    reasons: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    stage: str = "eligibility"
    is_specialization_course: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class RecommendationResult:
    """Kết quả gợi ý kế hoạch học tập toàn bộ"""
    
    student_id: str
    student_name: str
    current_semester: int
    next_semester: int
    study_goal: str
    
    # Danh sách các môn
    eligible_courses: List[RecommendedCourse] = field(default_factory=list)
    recommended_courses: List[RecommendedCourse] = field(default_factory=list)
    excluded_courses: List[ExcludedCourse] = field(default_factory=list)
    
    # Thống kê
    total_eligible_count: int = 0
    total_excluded_count: int = 0
    total_recommended_count: int = 0
    total_recommended_credits: int = 0
    
    # Hạn ngạch môn tự chọn
    elective_target_quotas: Dict[str, int] = field(default_factory=dict)
    elective_completed_counts: Dict[str, int] = field(default_factory=dict)
    elective_quota_remaining: Dict[str, int] = field(default_factory=dict)
    finalized_elective_counts: Dict[str, int] = field(default_factory=dict)
    
    # Cảnh báo và giải thích
    warnings: List[str] = field(default_factory=list)
    prerequisite_warnings: List[str] = field(default_factory=list)
    specialization_warning: str = ""
    beam_search_details: str = ""
    heuristic_formula: str = ""
    
    # Siêu dữ liệu
    generated_at: str = ""
    processing_time_ms: float = 0.0
    
    # Phân tích độ khó
    difficulty_analysis: Optional[Dict] = None
    
    def to_dict(self):
        result = asdict(self)
        # Chuyển danh sách lớp dữ liệu lồng nhau thành từ điển
        result['eligible_courses'] = [c.to_dict() for c in self.eligible_courses]
        result['recommended_courses'] = [c.to_dict() for c in self.recommended_courses]
        result['excluded_courses'] = [c.to_dict() for c in self.excluded_courses]
        return result


@dataclass
class BeamSearchState:
    """Trạng thái trong thuật toán tìm kiếm chùm"""
    
    selected_codes: set = field(default_factory=set)
    selected_courses: List[RecommendedCourse] = field(default_factory=list)
    credit: int = 0
    priority_score: float = 0.0
    
    # Theo dõi hạn ngạch
    elective_counts: Dict[str, int] = field(default_factory=lambda: {
        'general': 0,
        'physical': 0,
        'foundation': 0,
        'specialization': 0,
    })
    
    # Chỉ số phá hòa
    tie_break_random: float = 0.0
