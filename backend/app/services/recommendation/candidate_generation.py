"""Extracted existing behavior; operates on RecommendationEngine shared context."""

import random
from typing import Dict, List, Set, Optional, Tuple
from backend.app.models.student import StudentProfile
from backend.app.models.recommendation import RecommendedCourse, BeamSearchState, ExcludedCourse
from .constants import (
    ELECTIVE_QUOTA_KEYS,
)


class CandidateGenerationMixin:
    """Internal extraction boundary, not an independent Agent capability."""

    def _random_select_electives(self,
                                courses: List[RecommendedCourse],
                                remaining_quotas: Dict[str, int],
                                study_goal: str,
                                rng: random.Random,
                                seed_offset: int = 0) -> List[RecommendedCourse]:
        """Giữ toàn bộ ứng viên cho beam search, thêm nhiễu mạnh cho môn tự chọn để tạo đa dạng khi có seed_offset."""
        candidates = list(courses)

        if seed_offset != 0:
            for c in candidates:
                if c.total_priority_score < 10000:
                    noise = rng.randint(0, 5000)
                    c.total_priority_score += noise
                    c.heuristic_score += noise

        rng.shuffle(candidates)
        candidates.sort(key=lambda x: (
            -x.total_priority_score,
            not x.is_retake,
            -x.heuristic_score,
        ))
        return candidates

    def _beam_search_optimize(self,
                             student: StudentProfile,
                             candidates: List[RecommendedCourse],
                             completed_counts: Dict[str, int],
                             study_goal: str,
                             rng: random.Random,
                             passed_courses: Set[str]) -> Tuple[List[RecommendedCourse], List[ExcludedCourse]]:
        """Tìm kiếm chùm thật sự, có kiểm tra song hành, quota và tín chỉ."""
        effective_max_credits = self.max_credits

        excluded: Dict[Tuple[str, str], ExcludedCourse] = {}
        eligible_codes = {c.code for c in candidates}
        course_index = {c.code: c for c in candidates}

        def resolve_coreq_bundle(code_: str) -> Optional[Set[str]]:
            bundle = set()
            stack = [code_]
            while stack:
                ccc = stack.pop()
                if ccc in bundle:
                    continue
                bundle.add(ccc)
                coreqs = self.course_data.get(ccc, {}).get('corequisites', [])
                for co in coreqs:
                    if co in passed_courses:
                        continue
                    if co not in eligible_codes:
                        return None
                    if co not in bundle:
                        stack.append(co)
            return bundle

        def remember_excluded(course_: RecommendedCourse, rule: str, reason: str):
            key = (course_.code, rule)
            if key in excluded:
                return
            excluded[key] = ExcludedCourse(
                code=course_.code,
                name=course_.name,
                credits=course_.credits,
                recommended_semester=course_.recommended_semester,
                reasons=[reason],
                failed_rules=[rule],
                stage="beam_search",
                is_specialization_course=bool(self.course_data.get(course_.code, {}).get('specializations')),
            )

        def quota_fill_score(counts: Dict[str, int]) -> int:
            score = 0
            for cat in ELECTIVE_QUOTA_KEYS:
                remaining_quota = max(0, self.elective_quotas.get(cat, 0) - completed_counts.get(cat, 0))
                score += min(counts.get(cat, 0), remaining_quota)
            return score

        def state_key(state: BeamSearchState) -> Tuple[float, int, int, float]:
            return (
                state.priority_score,
                quota_fill_score(state.elective_counts),
                state.credit,
                state.tie_break_random,
            )

        initial_state = BeamSearchState(tie_break_random=rng.random())
        beam = [initial_state]
        best_state = initial_state
        max_iterations = len(candidates)

        for _ in range(max_iterations):
            new_states: List[BeamSearchState] = []

            for state in beam:
                for course in candidates:
                    if course.code in state.selected_codes:
                        continue

                    bundle_codes = resolve_coreq_bundle(course.code)
                    if bundle_codes is None:
                        remember_excluded(
                            course,
                            "corequisite",
                            "thiếu học phần song hành trong tập môn đủ điều kiện",
                        )
                        continue

                    if bundle_codes & state.selected_codes:
                        continue

                    bundle_courses = [course_index[bc] for bc in bundle_codes]
                    bundle_credit = sum(c.credits for c in bundle_courses)
                    if state.credit + bundle_credit > effective_max_credits:
                        remember_excluded(
                            course,
                            "max_credits",
                            f"thêm học phần/bundle sẽ vượt giới hạn {effective_max_credits} tín chỉ (mục tiêu: {study_goal})",
                        )
                        continue

                    next_elective_counts = dict(state.elective_counts)
                    quota_ok = True
                    for bc in bundle_codes:
                        cat = self.course_data.get(bc, {}).get('elective_category')
                        if cat in ELECTIVE_QUOTA_KEYS:
                            next_elective_counts[cat] = next_elective_counts.get(cat, 0) + 1
                            remaining_quota = max(0, self.elective_quotas.get(cat, 0) - completed_counts.get(cat, 0))
                            if next_elective_counts[cat] > remaining_quota:
                                quota_ok = False
                                break

                    if not quota_ok:
                        remember_excluded(
                            course,
                            "elective_quota",
                            "Nhóm học phần tự chọn đã hoàn thành.",
                        )
                        continue

                    next_courses = list(state.selected_courses)
                    for bc in sorted(bundle_codes):
                        if bc not in state.selected_codes:
                            next_courses.append(course_index[bc])

                    new_states.append(BeamSearchState(
                        selected_codes=set(state.selected_codes) | set(bundle_codes),
                        selected_courses=next_courses,
                        credit=state.credit + bundle_credit,
                        priority_score=state.priority_score + sum(c.total_priority_score for c in bundle_courses),
                        elective_counts=next_elective_counts,
                        tie_break_random=rng.random(),
                    ))

            if not new_states:
                break

            beam = sorted(beam + new_states, key=state_key, reverse=True)[:self.beam_width]
            if state_key(beam[0]) > state_key(best_state):
                best_state = beam[0]

        selected = sorted(
            best_state.selected_courses,
            key=lambda c: (-c.total_priority_score, c.code),
        )
        selected_codes = {course.code for course in selected}
        final_excluded = [
            item for item in excluded.values()
            if item.code not in selected_codes
        ]
        return selected, final_excluded
