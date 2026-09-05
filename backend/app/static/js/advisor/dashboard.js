/**
 * ADVISOR WORKSPACE CONTROLLER
 * Handles all 9 core advisor functionalities across standalone dedicated pages.
 */

window.AdvisorWorkspace = (function() {
    let studentsList = [];
    let selectedStudent = null;
    let currentScenario = 'standard';
    let recommendationData = null;
    let currentCompareIndex = 0;
    let selectedCourses = new Set();
    let currentSubTab = 'passed';
    let courseMap = new Map();
    const STUDENTS_CACHE_KEY = 'advisor.students.list.v1';
    const STATS_CACHE_KEY = 'advisor.stats.v1';
    const PLAN_DRAFT_KEY = 'advisor.plan.draft.v1';
    const STUDENTS_CACHE_TTL = 24 * 60 * 60 * 1000;

    function getPersistentStudentsCacheKey() {
        const cacheUser = document.body.dataset.cacheUser || 'advisor';
        return `${STUDENTS_CACHE_KEY}.${cacheUser}`;
    }

    function readPersistentStudentsCache() {
        try {
            const cached = JSON.parse(localStorage.getItem(getPersistentStudentsCacheKey()) || 'null');
            if (!cached || !Array.isArray(cached.data)) return null;
            if (Date.now() - Number(cached.savedAt || 0) > STUDENTS_CACHE_TTL) return null;
            return cached.data;
        } catch (_) {
            return null;
        }
    }

    function writePersistentStudentsCache(data) {
        try {
            localStorage.setItem(getPersistentStudentsCacheKey(), JSON.stringify({
                savedAt: Date.now(),
                data,
            }));
        } catch (_) {
            // Network loading remains available when browser storage is unavailable.
        }
    }

    function escapeHtml(unsafe) {
        return String(unsafe ?? '').replace(/[&<>'"]/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[char]));
    }

    function readSessionCache(key) {
        try {
            return JSON.parse(sessionStorage.getItem(key) || 'null');
        } catch (_) {
            return null;
        }
    }

    function writeSessionCache(key, value) {
        try {
            sessionStorage.setItem(key, JSON.stringify(value));
        } catch (_) {
            // The application still works when browser storage is unavailable.
        }
    }

    function getActiveRecommendedCourses() {
        if (!recommendationData) return [];
        const plan = getActiveRecommendationPlan();
        return Array.isArray(plan?.recommended_courses) ? plan.recommended_courses : [];
    }

    function getActiveRecommendationPlan() {
        if (!recommendationData) return null;
        return Array.isArray(recommendationData.plans)
            ? recommendationData.plans[currentCompareIndex]
            : recommendationData;
    }

    async function validateAdvisorPlanCourses(courses) {
        if (!selectedStudent) {
            return { success: false, error: 'Chưa chọn sinh viên để kiểm tra điều kiện học vụ.' };
        }
        try {
            const response = await fetch('/api/advisor/validate-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    student_id: selectedStudent.student_id,
                    recommended_courses: courses,
                }),
            });
            const result = await response.json();
            return {
                success: response.ok && result.success,
                error: result.error || 'Không thể kiểm tra điều kiện học vụ.',
                data: result.data,
            };
        } catch (error) {
            console.error('Plan validation failed:', error);
            return { success: false, error: 'Không thể kết nối đến máy chủ để kiểm tra điều kiện học vụ.' };
        }
    }

    function savePlanDraft() {
        if (!selectedStudent) return;
        const courses = getActiveRecommendedCourses()
            .filter(course => selectedCourses.has(course.course_code));
        const totalCredits = courses.reduce((sum, course) => sum + Number(course.credits || 0), 0);
        const notes = document.getElementById('planConfirmNotes')?.value || '';

        writeSessionCache(PLAN_DRAFT_KEY, {
            student_id: selectedStudent.student_id,
            student_name: selectedStudent.name || '',
            scenario: currentScenario,
            scenario_name: document.getElementById('resScenarioName')?.textContent || '',
            courses,
            selected_course_codes: Array.from(selectedCourses),
            total_credits: totalCredits,
            notes,
            updated_at: new Date().toISOString(),
        });
    }

    function restorePlanDraft() {
        if (!selectedStudent) return;
        const draft = readSessionCache(PLAN_DRAFT_KEY);
        if (!draft || String(draft.student_id) !== String(selectedStudent.student_id)) {
            selectedCourses.clear();
            updateSelectedLiveStats();
            renderConsultationPlan();
            return;
        }

        const courses = Array.isArray(draft.courses) ? draft.courses.map(normalizeRecommendedCourse) : [];
        selectedCourses = new Set(draft.selected_course_codes || courses.map(course => course.course_code));
        currentScenario = draft.scenario || 'standard';
        recommendationData = {
            recommended_courses: courses,
            total_recommended_count: courses.length,
            total_recommended_credits: Number(draft.total_credits || 0),
            summary_metrics: { plan_name: draft.scenario_name || 'Kế hoạch tư vấn' },
        };

        const notes = document.getElementById('planConfirmNotes');
        if (notes && !notes.value) notes.value = draft.notes || '';
        const reportNotes = document.getElementById('consultationNotes');
        if (reportNotes && !reportNotes.value) reportNotes.value = draft.notes || '';
        renderConsultationPlan();
        updateSelectedLiveStats();
    }

    function renderConsultationPlan() {
        const body = document.getElementById('consultationPlanBody');
        const tableWrap = document.getElementById('consultationPlanTableWrap');
        const empty = document.getElementById('consultationPlanEmpty');
        if (!body || !tableWrap || !empty) return;

        const courses = getActiveRecommendedCourses();
        if (!courses.length) {
            body.innerHTML = '';
            tableWrap.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        body.innerHTML = courses.map(course => {
            const code = escapeAdvisorHtml(course.course_code || '');
            const name = escapeAdvisorHtml(course.course_name || course.course_code || '');
            const reason = escapeAdvisorHtml(course.reason || 'Đề xuất theo điều kiện học vụ hiện tại');
            const checked = selectedCourses.has(course.course_code) ? 'checked' : '';
            return `
                <tr>
                    <td><input class="course-check" type="checkbox" value="${code}" data-credits="${Number(course.credits || 0)}" ${checked} onchange="AdvisorWorkspace.updateSelectedLiveStats()" aria-label="Chọn ${code}"></td>
                    <td><strong>${code}</strong></td>
                    <td>${name}</td>
                    <td>${Number(course.credits || 0)} TC</td>
                    <td class="text-sm">${reason}</td>
                    <td>
                        <div class="consultation-plan-actions">
                            <button type="button" class="btn-sm btn-outline" onclick="AdvisorWorkspace.editPlanCourseReason('${code}')">Sửa</button>
                            <button type="button" class="btn-sm btn-outline" style="--outline-action-color:#dc2626; --outline-action-hover-bg:#fef2f2; border-color:#fca5a5;" onclick="AdvisorWorkspace.removeCourseFromPlan('${code}')">Xóa</button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
        empty.style.display = 'none';
        tableWrap.style.display = 'block';
    }

    function openAddCourseModal() {
        const plan = getActiveRecommendationPlan();
        if (!selectedStudent || !plan) {
            alert('Hãy chọn sinh viên và chạy gợi ý trước khi thêm học phần.');
            return;
        }
        const inPlan = new Set(getActiveRecommendedCourses().map(course => String(course.course_code || '').toUpperCase()));
        const availableCourses = Array.from(courseMap.values())
            .filter(course => !inPlan.has(String(course.code || '').toUpperCase()))
            .sort((a, b) => String(a.code || '').localeCompare(String(b.code || '')));
        if (!availableCourses.length) {
            alert('Không còn học phần nào trong danh mục để thêm.');
            return;
        }

        const content = document.createElement('div');
        const selectLabel = document.createElement('label');
        selectLabel.textContent = 'Học phần cần bổ sung';
        selectLabel.htmlFor = 'addPlanCourseSelect';
        selectLabel.style.cssText = 'display:block; margin-bottom:8px; font-weight:700; color:#334155;';
        const select = document.createElement('select');
        select.id = 'addPlanCourseSelect';
        select.className = 'form-select';
        select.style.cssText = 'width:100%; margin-bottom:16px;';
        select.innerHTML = availableCourses.map(course =>
            `<option value="${escapeAdvisorHtml(course.code || '')}">${escapeAdvisorHtml(course.code || '')} — ${escapeAdvisorHtml(course.name || course.code || '')} (${Number(course.credits || 0)} TC)</option>`
        ).join('');
        const reasonLabel = document.createElement('label');
        reasonLabel.textContent = 'Lý do bổ sung';
        reasonLabel.htmlFor = 'addPlanCourseReason';
        reasonLabel.style.cssText = 'display:block; margin-bottom:8px; font-weight:700; color:#334155;';
        const reasonInput = document.createElement('textarea');
        reasonInput.id = 'addPlanCourseReason';
        reasonInput.className = 'form-textarea';
        reasonInput.rows = 3;
        reasonInput.maxLength = 500;
        reasonInput.placeholder = 'Ví dụ: Theo nguyện vọng hoặc cần hoàn thành nhóm tự chọn';
        reasonInput.style.width = '100%';
        content.append(selectLabel, select, reasonLabel, reasonInput);

        window.UIComponents?.showModalDialog({
            title: 'Thêm học phần vào kế hoạch',
            description: 'Học phần bổ sung sẽ được lưu vào kế hoạch tư vấn hiện tại.',
            content,
            actions: [
                { label: 'Hủy', variant: 'secondary' },
                { label: 'Xác nhận thêm', onClick: () => addCourseToPlan(select.value, reasonInput.value) },
            ],
        });
    }

    async function addCourseToPlan(courseCode, courseReason = '') {
        const code = String(courseCode || '').trim().toUpperCase();
        const plan = getActiveRecommendationPlan();
        if (!code || !plan) return;
        if (getActiveRecommendedCourses().some(course => course.course_code === code)) return;

        const course = courseMap.get(code);
        if (!course) {
            alert('Không tìm thấy học phần trong danh mục.');
            return;
        }
        const coursesToValidate = [
            ...getActiveRecommendedCourses().filter(item => selectedCourses.has(item.course_code)),
            { course_code: code },
        ];
        const validation = await validateAdvisorPlanCourses(coursesToValidate);
        if (!validation.success) {
            alert(`Không thể thêm học phần: ${validation.error}`);
            return;
        }

        plan.recommended_courses = plan.recommended_courses || [];
        plan.recommended_courses.push({
            course_code: code,
            course_name: course.name || code,
            credits: Number(course.credits || 0),
            course_type: course.course_type || 'Điều chỉnh bởi CVHT',
            reason: String(courseReason || '').trim() || 'Bổ sung thủ công bởi Cố vấn học tập',
            manually_added: true,
        });
        selectedCourses.add(code);
        renderConsultationPlan();
        updateSelectedLiveStats();
    }

    function editPlanCourseReason(courseCode) {
        const course = getActiveRecommendedCourses().find(item => item.course_code === courseCode);
        if (!course) return;

        const content = document.createElement('div');
        const label = document.createElement('label');
        label.htmlFor = 'editPlanCourseReasonInput';
        label.textContent = `Lý do tư vấn cho ${courseCode}`;
        label.style.cssText = 'display:block; margin-bottom:8px; font-weight:700; color:#334155;';
        const input = document.createElement('textarea');
        input.id = 'editPlanCourseReasonInput';
        input.className = 'form-textarea';
        input.rows = 4;
        input.maxLength = 500;
        input.value = course.reason || '';
        input.style.width = '100%';
        content.append(label, input);

        if (!window.UIComponents?.showModalDialog) return;
        window.UIComponents.showModalDialog({
            title: 'Cập nhật lý do tư vấn',
            description: 'Nội dung này sẽ được lưu cùng kế hoạch tư vấn của sinh viên.',
            content,
            actions: [
                { label: 'Hủy', variant: 'secondary' },
                {
                    label: 'Lưu thay đổi',
                    onClick: () => {
                        course.reason = input.value.trim() || 'Điều chỉnh bởi Cố vấn học tập';
                        renderConsultationPlan();
                        updateSelectedLiveStats();
                    },
                },
            ],
        });
        setTimeout(() => input.focus(), 0);
    }

    function removeCourseFromPlan(courseCode) {
        const plan = getActiveRecommendationPlan();
        if (!plan) return;
        const course = getActiveRecommendedCourses().find(item => item.course_code === courseCode);
        if (!course || !window.UIComponents?.showModalDialog) return;

        window.UIComponents.showModalDialog({
            title: 'Xóa học phần khỏi kế hoạch?',
            description: `${courseCode} — ${course.course_name || courseCode} sẽ không còn trong kế hoạch tư vấn hiện tại.`,
            content: 'Bạn vẫn có thể thêm lại học phần này trước khi chốt kế hoạch.',
            actions: [
                { label: 'Hủy', variant: 'secondary' },
                {
                    label: 'Xóa học phần',
                    variant: 'danger',
                    onClick: () => {
                        plan.recommended_courses = getActiveRecommendedCourses()
                            .filter(item => item.course_code !== courseCode);
                        selectedCourses.delete(courseCode);
                        renderConsultationPlan();
                        updateSelectedLiveStats();
                    },
                },
            ],
        });
    }
    let currentRiskFilter = 'ALL';

    function init() {
        document.body.dataset.activeRole = "advisor";
        initStarRatings();
        initRiskFilters();
        document.getElementById('planConfirmNotes')?.addEventListener('input', savePlanDraft);

        loadCourseCatalog();
        loadAllStudents().then(() => {
            const urlParams = new URLSearchParams(window.location.search);
            const targetId = urlParams.get('id');
            if (targetId) {
                selectStudent(targetId);
            }
        });
        loadCommunityEvaluations();
    }

    // --- 1. Load Stats ---
    async function loadAdvisorStats() {
        const renderStats = (data) => {
            if (!data) return;
            if (document.getElementById('statTotalStudents')) document.getElementById('statTotalStudents').textContent = data.total_students || 0;
            if (document.getElementById('statAtRiskStudents')) document.getElementById('statAtRiskStudents').textContent = data.at_risk_students || 0;
            if (document.getElementById('badgeAtRiskCount')) document.getElementById('badgeAtRiskCount').textContent = data.at_risk_students || 0;
            if (document.getElementById('statConsultations')) document.getElementById('statConsultations').textContent = data.total_consultations || 0;
            if (document.getElementById('statAvgRating')) document.getElementById('statAvgRating').textContent = `${data.average_rating || 5.0} / 5.0`;
        };
        renderStats(readSessionCache(STATS_CACHE_KEY));
        try {
            const res = await fetch('/api/advisor/stats');
            const json = await res.json();
            if (json.success && json.data) {
                writeSessionCache(STATS_CACHE_KEY, json.data);
                renderStats(json.data);
            }
        } catch (err) {
            console.error("Lỗi nạp thống kê CVHT:", err);
        }
    }

    async function loadCourseCatalog() {
        try {
            const res = await fetch('/api/students/courses');
            const json = await res.json();
            if (json.success && Array.isArray(json.data)) {
                json.data.forEach(c => {
                    if (c && c.code) {
                        courseMap.set(String(c.code).trim().toUpperCase(), c);
                    }
                });
            }
        } catch (err) {
            console.error("Lỗi nạp danh mục môn học:", err);
        }
    }

    // --- 2. Load Students & At-Risk Analysis (Chức năng 2 & 6) ---
    async function loadAllStudents() {
        const renderStudents = (data) => {
            studentsList = data;
            populateFilterDropdowns();
            populateStandaloneDropdowns();
            renderAtRiskPanel();
            applyFilters();
        };
        const cachedStudents = readSessionCache(STUDENTS_CACHE_KEY) || readPersistentStudentsCache();
        if (Array.isArray(cachedStudents) && cachedStudents.length > 0) {
            renderStudents(cachedStudents);
        }
        try {
            const res = await fetch('/api/students');
            const json = await res.json();
            if (json.success && Array.isArray(json.data)) {
                writeSessionCache(STUDENTS_CACHE_KEY, json.data);
                writePersistentStudentsCache(json.data);
                renderStudents(json.data);
            } else if (!Array.isArray(cachedStudents) || cachedStudents.length === 0) {
                if (document.getElementById('studentsTableBody')) {
                    document.getElementById('studentsTableBody').innerHTML = `<tr><td colspan="9" class="text-center text-red">Lỗi tải danh sách sinh viên: ${json.error || "Không có dữ liệu"}</td></tr>`;
                }
            }
        } catch (err) {
            console.error("Lỗi tải danh sách sinh viên:", err);
            if ((!Array.isArray(cachedStudents) || cachedStudents.length === 0) && document.getElementById('studentsTableBody')) {
                document.getElementById('studentsTableBody').innerHTML = `<tr><td colspan="9" class="text-center text-red">Không thể kết nối máy chủ dữ liệu sinh viên.</td></tr>`;
            }
        }
    }

    function populateFilterDropdowns() {
        const classSet = new Set();
        const specSet = new Set();
        studentsList.forEach(s => {
            if (s.academic_class) classSet.add(s.academic_class);
            if (s.specialization && s.specialization !== "Chưa chọn chuyên ngành") specSet.add(s.specialization);
        });

        const classSelect = document.getElementById('filterClass');
        if (classSelect) {
            classSelect.innerHTML = '<option value="">-- Tất cả lớp --</option>' + 
                Array.from(classSet).sort().map(c => `<option value="${c}">${c}</option>`).join('');
        }

        const specSelect = document.getElementById('filterSpec');
        if (specSelect) {
            specSelect.innerHTML = '<option value="">-- Tất cả chuyên ngành --</option>' + 
                Array.from(specSet).sort().map(sp => `<option value="${sp}">${sp}</option>`).join('');
        }
    }

    function populateStandaloneDropdowns() {
        const optionsHTML = '<option value="">-- Chọn sinh viên từ danh sách --</option>' +
            studentsList.map(s => `<option value="${s.student_id}">${s.student_id} - ${s.name || "SV"} (${s.academic_class || "-"})</option>`).join('');
        
        ['standaloneStudentSelect', 'standaloneScenSelect', 'standaloneConsSelect', 'standaloneRepSelect'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = optionsHTML;
                if (selectedStudent && selectedStudent.student_id) {
                    el.value = selectedStudent.student_id;
                }
                
                if (window.TomSelect) {
                    if (el.tomselect) {
                        el.tomselect.sync();
                    } else {
                        // Remove conflicting Tailwind form-select class before initializing
                        el.classList.remove('form-select');
                        new TomSelect(el, {
                            create: false,
                            sortField: { field: "text", direction: "asc" },
                            searchField: ['text', 'value'],
                            placeholder: "-- Chọn sinh viên từ danh sách --",
                            maxOptions: null
                        });
                    }
                }
            }
        });
    }

    function initRiskFilters() {
        const selectFilter = document.getElementById('riskStatusFilter');
        if (selectFilter) {
            selectFilter.addEventListener('change', (e) => {
                currentRiskFilter = e.target.value || 'ALL';
                renderAtRiskPanel();
            });
        }

        const riskBtns = document.querySelectorAll('[data-risk-filter]');
        if (riskBtns.length) {
            riskBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    riskBtns.forEach(b => {
                        b.classList.remove('active');
                        b.style.background = '#f8fafc';
                        b.style.color = '#475569';
                        b.style.borderColor = '#cbd5e1';
                    });
                    btn.classList.add('active');
                    btn.style.background = '#2563eb';
                    btn.style.color = '#ffffff';
                    btn.style.borderColor = '#2563eb';
                    currentRiskFilter = btn.getAttribute('data-risk-filter') || 'ALL';
                    renderAtRiskPanel();
                });
            });
        }
    }

    function renderAtRiskPanel() {
        const container = document.getElementById('atRiskContainer');
        if (!container) return;

        const hasFilterGroup = document.getElementById('riskFilterGroup') !== null;
        const isAtRiskPage = window.location.pathname.includes('/at-risk') || hasFilterGroup;

        const atRiskList = studentsList.filter(s => {
            if (!s.progress_status || s.progress_status === 'UNKNOWN' || s.progress_status === 'ON_TRACK') {
                return false;
            }
            if (!isAtRiskPage) {
                return s.progress_status === 'BEHIND_SCHEDULE';
            }
            if (currentRiskFilter === 'AT_RISK') return s.progress_status === 'AT_RISK';
            if (currentRiskFilter === 'BEHIND_SCHEDULE') return s.progress_status === 'BEHIND_SCHEDULE';
            return s.progress_status === 'AT_RISK' || s.progress_status === 'BEHIND_SCHEDULE';
        });

        if (atRiskList.length === 0) {
            container.innerHTML = `<div class="p-3 bg-green-50 text-green-700 rounded-lg w-100">🎉 Tuyệt vời! Hiện không có sinh viên nào trong danh sách bộ lọc này.</div>`;
            return;
        }

        container.innerHTML = atRiskList.map(s => {
            const gpa = parseFloat(s.gpa_accumulated || 0).toFixed(2);
            const failed = s.failed_courses_count || 0;
            const isBehind = s.progress_status === 'BEHIND_SCHEDULE';
            const riskLabel = isBehind ? 'Chậm tiến độ' : 'Có nguy cơ';
            const badgeBg = isBehind ? '#fee2e2' : '#fef08a';
            const badgeColor = isBehind ? '#991b1b' : '#854d0e';
            const badgeBorder = isBehind ? '#fca5a5' : '#fde047';
            const icon = isBehind ? '🚨' : '⚠️';
            const message = s.progress_message || `Nợ học phần: ${failed} môn`;
            return `
                <div class="risk-card">
                    <div class="risk-card__top">
                        <div>
                            <div class="risk-card__name">${s.name || "Sinh viên"}</div>
                            <div class="risk-card__id">${s.student_id} • ${s.academic_class || ""}</div>
                        </div>
                        <span class="risk-badge" style="background-color: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder}; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">${icon} ${riskLabel}</span>
                    </div>
                    <div class="risk-card__stats">
                        <span>GPA: <strong>${gpa}</strong></span>
                        <span>${message}</span>
                    </div>
                    <a href="/advisor/profile?id=${s.student_id}" class="risk-card__btn" style="text-decoration:none; text-align:center; display:block;">
                        👉 Tư vấn & Gỡ nút thắt ➔
                    </a>
                </div>
            `;
        }).join('');

        const actionLabels = [
            ['.btn-danger', 'Xóa hồ sơ sinh viên'],
            ['.btn-primary', 'Xem hồ sơ sinh viên'],
            ['.btn-success', 'Sinh kế hoạch học tập'],
        ];
        actionLabels.forEach(([selector, label]) => {
            tbody.querySelectorAll(selector).forEach(button => {
                button.setAttribute('title', label);
                button.setAttribute('aria-label', label);
            });
        });
    }

    function applyFilters() {
        const keyword = (document.getElementById('filterSearch')?.value || "").trim().toLowerCase();
        const cohort = document.getElementById('filterCohort')?.value || "";
        const cls = document.getElementById('filterClass')?.value || "";
        const spec = document.getElementById('filterSpec')?.value || "";
        const status = document.getElementById('filterStatus')?.value || "";

        const filtered = studentsList.filter(s => {
            if (keyword && !s.student_id.toLowerCase().includes(keyword) && !(s.name || "").toLowerCase().includes(keyword)) {
                return false;
            }
            if (cohort) {
                const yr = parseInt(s.year_admitted || 2023);
                if (cohort === "K65" && yr !== 2023) return false;
                if (cohort === "K66" && yr !== 2024) return false;
                if (cohort === "K67" && yr !== 2025) return false;
            }
            if (cls && s.academic_class !== cls) return false;
            if (spec && s.specialization !== spec) return false;
            if (status) {
                const gpa = parseFloat(s.gpa_accumulated || 0);
                const failed = parseInt(s.failed_courses_count || 0);
                const atRisk = s.progress_status === 'AT_RISK';
                const behindSchedule = s.progress_status === 'BEHIND_SCHEDULE';
                if (status === "at_risk" && !atRisk) return false;
                if (status === "behind" && !behindSchedule) return false;
                if (status === "debt" && !(s.progress_status === 'ON_TRACK' && failed > 0)) return false;
                if (status === "normal" && !(s.progress_status === 'ON_TRACK' && failed === 0)) return false;
            }
            return true;
        });

        if (document.getElementById('filterResultCount')) document.getElementById('filterResultCount').textContent = filtered.length;
        if (document.getElementById('filterTotalCount')) document.getElementById('filterTotalCount').textContent = studentsList.length;

        const tbody = document.getElementById('studentsTableBody');
        if (!tbody) return;

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-gray">Không tìm thấy sinh viên nào phù hợp với bộ lọc hiện tại.</td></tr>`;
            return;
        }

        tbody.innerHTML = filtered.map((s, idx) => {
            const gpa = parseFloat(s.gpa_accumulated || 0).toFixed(2);
            const credits = s.total_credits_accumulated || 0;
            const failed = parseInt(s.failed_courses_count || 0);
            
            let badgeClass = "normal";
            let badgeText = "Đúng tiến độ";
            if (s.progress_status === 'BEHIND_SCHEDULE') {
                badgeClass = "risk";
                badgeText = "Chậm tiến độ";
            } else if (s.progress_status === 'AT_RISK') {
                badgeClass = "warning";
                badgeText = "Có nguy cơ chậm tiến độ";
            } else if (s.progress_status === 'ON_TRACK' && failed > 0) {
                badgeClass = "debt";
                badgeText = "Có học phần cần học lại";
            } else if (s.progress_status === 'ON_TRACK') {
                badgeClass = "normal";
                badgeText = "Đúng tiến độ";
            } else if (gpa < 2.0 || failed > 1) {
                badgeClass = "risk";
                badgeText = "Nguy cơ chậm tiến độ";
            } else if (failed > 0) {
                badgeClass = "debt";
                badgeText = "Có học phần nợ";
            }

            const yr = parseInt(s.year_admitted || 2023);
            const cohortStr = yr === 2023 ? "K65" : (yr === 2024 ? "K66" : "K67");

            return `
                <tr>
                    <td>${idx + 1}</td>
                    <td><strong>${s.student_id}</strong></td>
                    <td>${s.name || "Chưa cập nhật"}</td>
                    <td>${s.academic_class || "-"} <small class="text-gray">(${cohortStr})</small></td>
                    <td>${s.specialization || "Chưa chọn"}</td>
                    <td><strong class="${gpa < 2.0 ? 'text-red' : ''}">${gpa}</strong></td>
                    <td>${credits} TC</td>
                    <td><span class="badge-status ${badgeClass}">${badgeText}</span></td>
                    <td class="text-center" style="white-space: nowrap;">
                        <button type="button" class="btn-sm btn-danger" style="margin:2px; display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; padding:0; border-radius:8px;" title="Xóa hồ sơ sinh viên" onclick='AdvisorWorkspace.deleteStudent(${JSON.stringify(String(s.student_id))}, ${JSON.stringify(s.name || "Sinh viên")})'>
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>
                        <a href="/advisor/profile?id=${s.student_id}" class="btn-sm btn-primary" title="Xem hồ sơ sinh viên" style="text-decoration:none; margin:2px; display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; padding:0; border-radius:8px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                        </a>
                        <a href="/advisor/scenarios?id=${s.student_id}" class="btn-sm btn-success" title="Sinh kế hoạch học tập" style="text-decoration:none; margin:2px; display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; padding:0; border-radius:8px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M3 5h4"/></svg>
                        </a>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function resetFilters() {
        if (document.getElementById('filterSearch')) document.getElementById('filterSearch').value = "";
        if (document.getElementById('filterCohort')) document.getElementById('filterCohort').value = "";
        if (document.getElementById('filterClass')) document.getElementById('filterClass').value = "";
        if (document.getElementById('filterSpec')) document.getElementById('filterSpec').value = "";
        if (document.getElementById('filterStatus')) document.getElementById('filterStatus').value = "";
        applyFilters();
    }

    async function deleteStudent(studentId, studentName) {
        const confirmation = `Bạn có chắc muốn xóa hồ sơ của ${studentName || 'sinh viên'} (${studentId})? Hành động này không thể hoàn tác.`;
        if (!window.confirm(confirmation)) return;

        try {
            const response = await fetch(`/api/students/${encodeURIComponent(studentId)}`, { method: 'DELETE' });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || 'Không thể xóa hồ sơ sinh viên.');

            studentsList = studentsList.filter(student => String(student.student_id) !== String(studentId));
            sessionStorage.removeItem(STUDENTS_CACHE_KEY);
            sessionStorage.removeItem(STATS_CACHE_KEY);
            localStorage.removeItem(getPersistentStudentsCacheKey());
            if (selectedStudent && String(selectedStudent.student_id) === String(studentId)) selectedStudent = null;
            applyFilters();
            window.alert(result.message || 'Đã xóa hồ sơ sinh viên.');
        } catch (error) {
            console.error('Lỗi xóa hồ sơ sinh viên:', error);
            window.alert(error.message || 'Không thể kết nối máy chủ để xóa hồ sơ sinh viên.');
        }
    }

    // --- 3. Student Profile Selection (Chức năng 3) ---
    async function selectStudent(studentId) {
        try {
            if (courseMap.size === 0) {
                await loadCourseCatalog();
            }
            const res = await fetch(`/api/students/${studentId}`);
            const json = await res.json();
            if (json.success && json.data) {
                selectedStudent = json.data;
                updateProfileUI();
                updateScenarioStudentUI();
                if (window.location.pathname.includes('/advisor/consultation') || window.location.pathname.includes('/advisor/reports')) {
                    restorePlanDraft();
                }
                loadConsultationHistory(studentId);
                
                // Sync select boxes across pages
                ['standaloneStudentSelect', 'standaloneScenSelect', 'standaloneConsSelect', 'standaloneRepSelect'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = studentId;
                });
            } else {
                alert(`Không thể lấy chi tiết sinh viên ${studentId}: ${json.error}`);
            }
        } catch (err) {
            console.error("Lỗi lấy chi tiết sinh viên:", err);
            alert("Lỗi kết nối khi lấy dữ liệu chi tiết sinh viên.");
        }
    }

    function updateProfileUI() {
        if (!selectedStudent) return;
        if (document.getElementById('profileEmptyState')) document.getElementById('profileEmptyState').style.display = 'none';
        if (document.getElementById('profileBanner')) document.getElementById('profileBanner').style.display = 'flex';
        if (document.getElementById('profileContent')) document.getElementById('profileContent').style.display = 'block';

        const s = selectedStudent;
        if (document.getElementById('profAvatar')) document.getElementById('profAvatar').textContent = (s.name || "SV").substring(0, 2).toUpperCase();
        if (document.getElementById('profName')) document.getElementById('profName').textContent = s.name || "Chưa cập nhật tên";
        if (document.getElementById('profId')) document.getElementById('profId').textContent = s.student_id;
        if (document.getElementById('profClass')) document.getElementById('profClass').textContent = s.academic_class || "Chưa xếp lớp";
        if (document.getElementById('profMajor')) document.getElementById('profMajor').textContent = s.major || "CNTT";
        if (document.getElementById('profSpec')) document.getElementById('profSpec').textContent = s.specialization || "Chưa chọn";
        if (document.getElementById('profGoal')) document.getElementById('profGoal').textContent = s.study_goal || "Đúng tiến độ";

        const gpa = parseFloat(s.gpa_accumulated || 0).toFixed(2);
        if (document.getElementById('profGpa')) document.getElementById('profGpa').textContent = gpa;
        if (document.getElementById('profCredits')) document.getElementById('profCredits').textContent = `${s.total_credits_accumulated || 0} TC`;
        if (document.getElementById('profSem')) document.getElementById('profSem').textContent = `Học kỳ ${s.current_semester || 1}`;

        let badgeClass = "normal";
        let badgeText = "Đúng tiến độ";
        const failed = (s.failed_courses || []).length;
        const progressStatus = s.progress_analysis?.progress_status;
        if (progressStatus === 'BEHIND_SCHEDULE') {
            badgeClass = "risk"; badgeText = "Chậm tiến độ";
        } else if (progressStatus === 'AT_RISK') {
            badgeClass = "risk"; badgeText = "Nguy cơ chậm tiến độ";
        } else if (failed > 0) {
            badgeClass = "debt"; badgeText = "Có học phần nợ";
        } else if (false) {
            badgeClass = "good"; badgeText = "Khá / Giỏi";
        }
        if (progressStatus === 'BEHIND_SCHEDULE') {
            badgeClass = "risk";
            badgeText = "Sinh viên chậm tiến độ";
        } else if (progressStatus === 'AT_RISK') {
            badgeClass = "warning";
            badgeText = "Sinh viên có nguy cơ chậm tiến độ";
        } else if (failed > 0) {
            badgeClass = "debt";
            badgeText = "Có học phần nợ";
        } else {
            badgeClass = "normal";
            badgeText = "Đúng tiến độ";
        }
        if (document.getElementById('profStatusTag')) document.getElementById('profStatusTag').innerHTML = `<span class="badge-status profile-status ${badgeClass}">${badgeText}</span>`;

        const passedCount = Object.keys(s.passed_courses || {}).length || (Array.isArray(s.passed_courses) ? s.passed_courses.length : 0);
        const failedCount = (s.failed_courses || []).length;
        const historyCount = (s.course_attempts || []).length;

        if (document.getElementById('countPassed')) document.getElementById('countPassed').textContent = passedCount;
        if (document.getElementById('countFailed')) document.getElementById('countFailed').textContent = failedCount;
        if (document.getElementById('countHistory')) document.getElementById('countHistory').textContent = historyCount;

        renderCourseHistory();
    }

    function switchSubTab(subId) {
        currentSubTab = subId;
        document.querySelectorAll('.sub-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sub === subId);
        });
        renderCourseHistory();
    }

    function getCourseDetails(code, defaultName) {
        const cleanCode = String(code || "").trim().toUpperCase();
        const info = courseMap.get(cleanCode);
        let name = defaultName;
        if (info && info.name && info.name !== cleanCode) {
            name = info.name;
        } else if (!name || name === cleanCode) {
            name = cleanCode;
        }
        const credits = (info && info.credits !== undefined && info.credits !== "") ? info.credits : "-";
        return { name, credits };
    }

    function getCourseGradeAndStatusDisplay(code, rawGrade, s) {
        let status = "Đạt";
        let specified = true;
        let grade = rawGrade;

        if (s && s.course_statuses && s.course_statuses[code]) {
            status = s.course_statuses[code];
        }
        if (s && s.course_grade_specified && s.course_grade_specified[code] !== undefined) {
            specified = s.course_grade_specified[code];
        }

        if (s && Array.isArray(s.course_attempts)) {
            const att = s.course_attempts.find(a => (a.course_code === code || a.code === code));
            if (att) {
                if (att.status) status = att.status;
                if (att.grade_specified !== undefined) specified = att.grade_specified;
                if (grade === undefined || grade === "-" || grade === null) grade = att.grade;
            }
        }

        let gradeDisplay = "-";
        if (status === "Không tính điểm" || status === "Miễn") {
            gradeDisplay = status;
        } else if (status === "Đạt" && (grade === 0 || grade === 0.0 || grade === "0" || grade === "0.0" || specified === false || grade === undefined || grade === null || grade === "-")) {
            gradeDisplay = "Điểm đạt";
        } else if (grade !== undefined && grade !== null && grade !== "-" && grade !== "") {
            const num = Number(grade);
            gradeDisplay = isNaN(num) ? grade : (Number.isInteger(num) ? num : num.toFixed(1));
        } else {
            gradeDisplay = status || "-";
        }

        return { gradeDisplay, status };
    }

    function renderCourseHistory() {
        if (!selectedStudent) return;
        const tbody = document.getElementById('courseHistoryBody');
        if (!tbody) return;

        const s = selectedStudent;
        const attempts = s.course_attempts || [];
        const gradesMap = s.course_grades || {};
        const passedMap = s.passed_courses || {};
        const failedList = s.failed_courses || [];

        const formatSemester = (attempt) => {
            if (!attempt) return "Chưa cập nhật";
            const semester = Number(attempt.semester_taken || 0);
            if (semester === 1) return "Học kỳ 1";
            if (semester === 2) return "Học kỳ 2";
            if (semester === 3) return "Học kỳ 3";
            return "Chưa xác định";
        };

        const formatAcademicYear = (attempt) => attempt?.academic_year || "Chưa cập nhật";
        const formatAttemptNumber = (attempt) => attempt ? `Lần ${attempt.attempt_number || 1}` : "Chưa cập nhật";

        const findAttempt = (courseCode, passedOnly = false) => {
            const matchingAttempts = attempts
                .filter((attempt) => String(attempt.course_code || "").trim() === String(courseCode).trim())
                .filter((attempt) => !passedOnly || ["Đạt", "Miễn", "Không tính điểm"].includes(attempt.status));
            return matchingAttempts.sort((a, b) =>
                Number(b.semester_taken || 0) - Number(a.semester_taken || 0)
                || Number(b.attempt_number || 1) - Number(a.attempt_number || 1)
            )[0];
        };

        const attemptOrder = (attempt, code = "") => {
            const yearMatch = String(attempt?.academic_year || "").match(/^(\d{4})/);
            const year = yearMatch ? Number(yearMatch[1]) : Number.MAX_SAFE_INTEGER;
            const globalTerm = Number(attempt?.actual_term || attempt?.semester_taken || 0);
            const term = globalTerm > 0 ? ((globalTerm - 1) % 3) + 1 : Number.MAX_SAFE_INTEGER;
            return [year, term, String(code || attempt?.course_code || "").toUpperCase(), Number(attempt?.attempt_number || 1)];
        };

        const compareAttempts = (left, right) => {
            const a = attemptOrder(left.attempt, left.code);
            const b = attemptOrder(right.attempt, right.code);
            return a[0] - b[0] || a[1] - b[1] || a[2].localeCompare(b[2], "vi") || a[3] - b[3];
        };

        let rowsHTML = "";
        if (currentSubTab === 'passed') {
            const keys = Array.isArray(passedMap) ? passedMap : Object.keys(passedMap);
            if (keys.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-gray">Sinh viên chưa có học phần nào đạt hoặc miễn.</td></tr>`;
                return;
            }
            const orderedKeys = keys.map(code => ({ code, attempt: findAttempt(code, true) }))
                .sort(compareAttempts).map(item => item.code);
            rowsHTML = orderedKeys.map(code => {
                const rawName = (typeof passedMap === 'object' && !Array.isArray(passedMap) && passedMap[code]) ? passedMap[code] : code;
                const { name, credits } = getCourseDetails(code, rawName);
                const { gradeDisplay, status } = getCourseGradeAndStatusDisplay(code, gradesMap[code], s);
                const attempt = findAttempt(code, true);
                return `
                    <tr>
                        <td><strong>${code}</strong></td>
                        <td>${name}</td>
                        <td class="text-center" style="text-align: center;">${credits}</td>
                        <td class="text-center" style="text-align: center;"><strong class="text-green">${gradeDisplay}</strong></td>
                        <td class="text-center" style="text-align: center;"><span class="badge-status normal">${status}</span></td>
                        <td>${formatSemester(attempt)}</td>
                        <td>${formatAcademicYear(attempt)}</td>
                        <td>${formatAttemptNumber(attempt)}</td>
                    </tr>
                `;
            }).join('');
        } else if (currentSubTab === 'failed') {
            if (failedList.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-green">🎉 Không có học phần nào bị nợ hoặc chưa đạt.</td></tr>`;
                return;
            }
            const orderedFailed = failedList.map(item => {
                const code = typeof item === 'object' ? item.course_code : item;
                return { item, code, attempt: findAttempt(code) };
            }).sort(compareAttempts).map(entry => entry.item);
            rowsHTML = orderedFailed.map(item => {
                const code = typeof item === 'object' ? item.course_code : item;
                const rawName = typeof item === 'object' ? item.course_name : code;
                const { name, credits } = getCourseDetails(code, rawName);
                const { gradeDisplay, status } = getCourseGradeAndStatusDisplay(code, gradesMap[code], s);
                const attempt = findAttempt(code);
                return `
                    <tr>
                        <td><strong>${code}</strong></td>
                        <td>${name}</td>
                        <td class="text-center" style="text-align: center;">${credits}</td>
                        <td class="text-center" style="text-align: center;"><strong class="text-red">${gradeDisplay}</strong></td>
                        <td class="text-center" style="text-align: center;"><span class="badge-status risk">${status !== 'Đạt' ? status : 'Chưa đạt'}</span></td>
                        <td>${formatSemester(attempt)}</td>
                        <td>${formatAcademicYear(attempt)}</td>
                        <td>${formatAttemptNumber(attempt)}</td>
                    </tr>
                `;
            }).join('');
        } else {
            if (attempts.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-gray">Chưa có lịch sử học phần chi tiết.</td></tr>`;
                return;
            }
            const orderedAttempts = attempts.map(attempt => ({ attempt, code: attempt.course_code }))
                .sort(compareAttempts).map(item => item.attempt);
            rowsHTML = orderedAttempts.map(a => {
                const { name, credits } = getCourseDetails(a.course_code, a.course_name);
                const isPass = a.status === 'Đạt' || a.status === 'Miễn' || a.status === 'Không tính điểm';
                let gradeDisplay = "-";
                if (a.status === "Không tính điểm" || a.status === "Miễn") {
                    gradeDisplay = a.status;
                } else if (a.status === "Đạt" && (a.grade === 0 || a.grade === 0.0 || a.grade === "0" || a.grade_specified === false || a.grade === undefined || a.grade === null)) {
                    gradeDisplay = "Điểm đạt";
                } else if (a.grade !== undefined && a.grade !== null && a.grade !== "") {
                    const num = Number(a.grade);
                    gradeDisplay = isNaN(num) ? a.grade : (Number.isInteger(num) ? num : num.toFixed(1));
                } else {
                    gradeDisplay = a.status || "-";
                }
                return `
                    <tr>
                        <td><strong>${a.course_code}</strong></td>
                        <td>${name}</td>
                        <td class="text-center" style="text-align: center;">${credits}</td>
                        <td class="text-center" style="text-align: center;"><strong class="${isPass ? 'text-green' : 'text-red'}">${gradeDisplay}</strong></td>
                        <td class="text-center" style="text-align: center;"><span class="badge-status ${isPass ? 'normal' : 'risk'}">${a.status || (isPass ? 'Đạt' : 'Chưa đạt')}</span></td>
                        <td>${formatSemester(a)}</td>
                        <td>${formatAcademicYear(a)}</td>
                        <td>${formatAttemptNumber(a)}</td>
                    </tr>
                `;
            }).join('');
        }
        tbody.innerHTML = rowsHTML;
    }

    // --- 4. Scenarios & Recommendation Engine (Chức năng 4, 5, 8) ---
    function updateScenarioStudentUI() {
        if (!selectedStudent) return;
        if (document.getElementById('scenStudentName')) document.getElementById('scenStudentName').textContent = selectedStudent.name || "Chưa cập nhật";
        if (document.getElementById('scenStudentId')) document.getElementById('scenStudentId').textContent = selectedStudent.student_id;
        if (document.getElementById('repStudentName')) document.getElementById('repStudentName').textContent = selectedStudent.name || "Chưa cập nhật";
        if (document.getElementById('repStudentId')) document.getElementById('repStudentId').textContent = selectedStudent.student_id;

        if (document.getElementById('scenariosEmptyState')) document.getElementById('scenariosEmptyState').style.display = 'none';
        if (document.getElementById('scenariosContent')) document.getElementById('scenariosContent').style.display = 'block';
    }

    function selectScenario(scenType) {
        currentScenario = scenType;
        document.querySelectorAll('.scenario-card').forEach(card => card.classList.remove('active'));
        if (scenType === 'standard') document.getElementById('cardScenStandard')?.classList.add('active');
        if (scenType === 'compare') document.getElementById('cardScenCompare')?.classList.add('active');
    }

    function normalizeRecommendedCourse(course) {
        const item = course || {};
        const code = item.course_code || item.code || '';
        const name = item.course_name || item.name || code;
        const reason = item.reason || (Array.isArray(item.reasons) ? item.reasons.join('; ') : '');
        return { ...item, course_code: code, course_name: name, reason };
    }

    function normalizeRecommendationPlan(plan) {
        const item = plan || {};
        return {
            ...item,
            recommended_courses: (item.recommended_courses || []).map(normalizeRecommendedCourse),
            excluded_courses: (item.excluded_courses || []).map(normalizeRecommendedCourse),
        };
    }

    function normalizeRecommendationData(data) {
        if (Array.isArray(data?.plans)) {
            return { ...data, plans: data.plans.map(normalizeRecommendationPlan) };
        }
        return normalizeRecommendationPlan(data);
    }

    function setRecommendationLoading(isLoading) {
        if (window.UIComponents?.setLoading) {
            window.UIComponents.setLoading('algoLoading', isLoading);
        } else if (document.getElementById('algoLoading')) {
            document.getElementById('algoLoading').style.display = isLoading ? 'block' : 'none';
        }
    }

    async function runRecommendation() {
        if (!selectedStudent) {
            alert("Vui lòng chọn một sinh viên trước khi chạy thuật toán.");
            return;
        }

        setRecommendationLoading(true);
        if (document.getElementById('algoResults')) document.getElementById('algoResults').style.display = 'none';

        const payload = {
            student_id: selectedStudent.student_id,
            compare: (currentScenario === 'compare'),
            randomize: (currentScenario === 'compare'),
            scenario: currentScenario
        };

        try {
            const res = await fetch('/api/recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            setRecommendationLoading(false);

            if (json.success && json.data) {
                recommendationData = normalizeRecommendationData(json.data);
                currentCompareIndex = 0;
                renderRecommendationResults();
                if (document.getElementById('algoResults')) document.getElementById('algoResults').style.display = 'block';
                savePlanDraft();
            } else {
                alert(`Lỗi chạy thuật toán gợi ý: ${json.error || "Không rõ nguyên nhân"}`);
            }
        } catch (err) {
            console.error("Lỗi gọi API gợi ý:", err);
            setRecommendationLoading(false);
            alert("Lỗi kết nối đến máy chủ thuật toán gợi ý.");
        }
    }

    function renderRecommendationResults() {
        if (!recommendationData) return;

        let activePlan = null;
        const compareBar = document.getElementById('compareTabsBar');

        if (Array.isArray(recommendationData.plans) && recommendationData.plans.length > 0) {
            if (compareBar) {
                compareBar.style.display = 'flex';
                compareBar.innerHTML = recommendationData.plans.map((p, idx) => `
                    <button type="button" class="btn-compare-tab ${idx === currentCompareIndex ? 'active' : ''}" onclick="AdvisorWorkspace.switchComparePlan(${idx})">
                        📌 Phương án ${idx + 1}: ${p.summary_metrics?.plan_name || 'Thay thế ' + idx} (${p.total_recommended_credits} TC)
                    </button>
                `).join('');
            }
            activePlan = recommendationData.plans[currentCompareIndex];
        } else {
            if (compareBar) compareBar.style.display = 'none';
            activePlan = recommendationData;
        }

        if (!activePlan) return;

        if (document.getElementById('resCourseCount')) document.getElementById('resCourseCount').textContent = activePlan.total_recommended_count || (activePlan.recommended_courses || []).length;
        if (document.getElementById('resCreditCount')) document.getElementById('resCreditCount').textContent = activePlan.total_recommended_credits || 0;
        if (document.getElementById('resScenarioName')) document.getElementById('resScenarioName').textContent = activePlan.summary_metrics?.plan_name || 'Tối ưu chuẩn';

        const excludedList = activePlan.excluded_courses || [];
        if (document.getElementById('resExcludedCount')) document.getElementById('resExcludedCount').textContent = excludedList.length;
        
        const recContainer = document.getElementById('recommendedCoursesContainer');
        if (recContainer) recContainer.style.display = 'block';
        const exPanel = document.getElementById('excludedPanel');
        if (exPanel) exPanel.style.display = 'none';

        renderExcludedCourses(excludedList);

        const recList = activePlan.recommended_courses || [];
        selectedCourses.clear();
        recList.forEach(c => selectedCourses.add(c.course_code));

        const recBody = document.getElementById('recTableBody');
        if (recBody) {
            if (recList.length === 0) {
                recBody.innerHTML = `<tr><td colspan="7" class="text-center text-red">Thuật toán không tìm thấy môn học nào phù hợp với điều kiện và giới hạn tín chỉ hiện tại.</td></tr>`;
            } else {
                recBody.innerHTML = recList.map(c => {
                    const isMandatory = c.total_priority_score >= 10000 || c.course_type === 'Bắt buộc';
                    const groupBadge = isMandatory ? '<span class="badge-status risk">Bắt buộc</span>' : '<span class="badge-status good">Tự chọn</span>';
                    return `
                        <tr>
                            <td class="text-center">
                                <input type="checkbox" class="course-check" value="${c.course_code}" data-credits="${c.credits || 0}" checked onchange="AdvisorWorkspace.updateSelectedLiveStats()">
                            </td>
                            <td><strong>${c.course_code}</strong></td>
                            <td>${c.course_name || c.course_code}</td>
                            <td><strong>${c.credits || 0}</strong> TC</td>
                            <td>${groupBadge}</td>
                            <td class="text-sm">${c.reason || "Đủ điều kiện tiên quyết & đúng kỳ mở môn"}</td>
                            <td class="text-center">
                                <button type="button" class="btn-sm btn-outline" onclick="AdvisorWorkspace.openPrereqModal('${c.course_code}')">
                                    🔍 Xem chuỗi
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            }
        }
        updateSelectedLiveStats();
    }

    function switchComparePlan(index) {
        currentCompareIndex = index;
        renderRecommendationResults();
    }

    function toggleExcludedPanel() {
        const p = document.getElementById('excludedPanel');
        const rec = document.getElementById('recommendedCoursesContainer');
        if (p) {
            const isHidden = (p.style.display === 'none');
            p.style.display = isHidden ? 'block' : 'none';
            if (rec) {
                rec.style.display = isHidden ? 'none' : 'block';
            }
        }
    }

    function showExcludedCoursesByRule(rule) {
        const section = document.getElementById('excludedPanel');
        const tbody = document.getElementById('excludedCoursesList');
        const detail = document.getElementById('excludedCoursesDetail');
        const detailHint = document.getElementById('excludedDetailHint');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!section || !tbody || !detail || !detailHint || !toggleBtn || !summaryGrid) return;

        let list = [];
        try { list = JSON.parse(section.dataset.excludedCourses || '[]'); } catch (e) {}

        const ruleMeta = {
            prerequisite: 'Thiếu tiên quyết',
            open_semester: 'Sai kỳ mở môn',
            recommended_semester: 'Chưa đến kỳ khuyến nghị',
            specialization: 'Chuyên ngành chưa xét/không khớp',
            major: 'Không thuộc ngành học',
            already_passed: 'Đã hoàn thành',
            noise_course: 'Ngoài phạm vi gợi ý',
            national_defense: 'Giáo dục quốc phòng',
            elective_quota: 'Nhóm học phần tự chọn đã hoàn thành',
            max_credits: 'Vượt giới hạn tín chỉ',
            corequisite: 'Thiếu môn song hành',
            forced_semester: 'Sai ràng buộc học kỳ',
            course_credit_limit: 'Tín chỉ học phần quá lớn',
        };

        const detailList = list.filter(course => ((course.failed_rules || [])[0] || 'other') === rule)
                               .sort((a, b) => (a.course_code || "").localeCompare(b.course_code || ""));
            
        tbody.innerHTML = detailList.map((course, index) => {
            const reasonText = course.reason || (Array.isArray(course.reasons) ? course.reasons.join(', ') : '-');
            return `
                <tr>
                    <td class="text-center">${index + 1}</td>
                    <td class="text-center font-bold"><strong>${escapeHtml(course.course_code || '-')}</strong></td>
                    <td>${escapeHtml(course.course_name || '-')}</td>
                    <td style="color: #dc2626;">⚠️ ${escapeHtml(reasonText)}</td>
                </tr>
            `;
        }).join('');

        summaryGrid.querySelectorAll('.ui-chip').forEach(chip => {
            chip.classList.toggle('is-active', chip.dataset.rule === rule);
        });
        section.dataset.selectedRule = rule;
        detail.style.display = 'block';
        detailHint.style.display = 'block';
        detailHint.textContent = `${ruleMeta[rule] || rule}: ${detailList.length} học phần`;
        toggleBtn.style.display = 'inline-block';
        toggleBtn.textContent = 'Ẩn chi tiết';
    }

    function toggleExcludedCoursesDetail() {
        const detail = document.getElementById('excludedCoursesDetail');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const detailHint = document.getElementById('excludedDetailHint');
        const section = document.getElementById('excludedPanel');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!detail || !toggleBtn || !detailHint || !section || !summaryGrid) return;

        detail.style.display = 'none';
        detailHint.style.display = 'none';
        toggleBtn.style.display = 'none';
        section.dataset.selectedRule = '';
        summaryGrid.querySelectorAll('.ui-chip').forEach(chip => chip.classList.remove('is-active'));
    }

    function renderExcludedCourses(courses) {
        const section = document.getElementById('excludedPanel');
        const countEl = document.getElementById('excludedCoursesCount');
        const tbody = document.getElementById('excludedCoursesList');
        const empty = document.getElementById('excludedEmptyState');
        const detail = document.getElementById('excludedCoursesDetail');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        const detailHint = document.getElementById('excludedDetailHint');
        if (!section || !countEl || !tbody || !empty || !detail || !toggleBtn || !summaryGrid || !detailHint) return;

        const hiddenRules = new Set(['noise_course', 'major']);
        const list = (Array.isArray(courses) ? courses : []).filter(course => {
            const rule = (course.failed_rules || [])[0] || 'other';
            return !hiddenRules.has(rule);
        });
        
        section.dataset.excludedCourses = JSON.stringify(list);
        section.dataset.selectedRule = '';
        countEl.textContent = String(list.length);
        tbody.innerHTML = '';
        summaryGrid.innerHTML = '';
        detail.style.display = 'none';
        detailHint.style.display = 'none';
        toggleBtn.textContent = 'Ẩn chi tiết';

        if (!list.length) {
            empty.style.display = 'block';
            toggleBtn.style.display = 'none';
            return;
        }

        const ruleMeta = {
            prerequisite: { label: 'Thiếu tiên quyết', className: 'red' },
            open_semester: { label: 'Sai kỳ mở môn', className: 'purple' },
            recommended_semester: { label: 'Chưa đến kỳ khuyến nghị', className: 'green' },
            specialization: { label: 'Chuyên ngành chưa xét/không khớp', className: 'blue' },
            major: { label: 'Không thuộc ngành học', className: 'pink' },
            already_passed: { label: 'Đã hoàn thành', className: 'gray' },
            noise_course: { label: 'Ngoài phạm vi gợi ý', className: 'gray' },
            national_defense: { label: 'Giáo dục quốc phòng', className: 'teal' },
            elective_quota: { label: 'Nhóm tự chọn đã hoàn thành', className: 'cyan' },
            max_credits: { label: 'Vượt giới hạn tín chỉ', className: 'indigo' },
            corequisite: { label: 'Thiếu môn song hành', className: 'amber' },
            forced_semester: { label: 'Sai ràng buộc học kỳ', className: 'orange' },
            course_credit_limit: { label: 'Tín chỉ quá lớn', className: 'rose' },
        };

        const countsByRule = {};
        list.forEach(course => {
            const rule = (course.failed_rules || [])[0] || 'other';
            countsByRule[rule] = (countsByRule[rule] || 0) + 1;
        });

        summaryGrid.innerHTML = Object.entries(countsByRule).map(([rule, count]) => {
            const meta = ruleMeta[rule] || { label: rule, className: 'normal' };
            return `
                <button type="button" class="ui-chip ui-chip--${meta.className}" data-rule="${escapeHtml(rule)}" onclick="AdvisorWorkspace.showExcludedCoursesByRule('${escapeHtml(rule)}')">
                    ${escapeHtml(meta.label)} <span class="ui-chip__count">${count}</span>
                </button>
            `;
        }).join('');

        empty.style.display = 'none';
        toggleBtn.style.display = 'none';
    }

    function updateSelectedLiveStats() {
        let count = 0;
        let credits = 0;
        const checkboxes = document.querySelectorAll('.course-check');
        if (checkboxes.length > 0) {
            selectedCourses.clear();
            document.querySelectorAll('.course-check:checked').forEach(chk => {
                count++;
                credits += parseInt(chk.dataset.credits || 0);
                selectedCourses.add(chk.value);
            });
        } else {
            const selected = getActiveRecommendedCourses()
                .filter(course => selectedCourses.has(course.course_code));
            count = selected.length;
            credits = selected.reduce((sum, course) => sum + Number(course.credits || 0), 0);
        }
        if (document.getElementById('liveSelectedCount')) document.getElementById('liveSelectedCount').textContent = count;
        if (document.getElementById('liveSelectedCredits')) document.getElementById('liveSelectedCredits').textContent = credits;
        savePlanDraft();
    }

    function goToConsultation() {
        if (!selectedStudent) {
            alert('Vui lòng chọn sinh viên trước khi chốt kế hoạch.');
            return;
        }
        updateSelectedLiveStats();
        window.location.href = `/advisor/consultation?id=${encodeURIComponent(selectedStudent.student_id)}`;
    }

    function goToScenarios() {
        const id = selectedStudent?.student_id;
        window.location.href = id
            ? `/advisor/scenarios?id=${encodeURIComponent(id)}`
            : '/advisor/scenarios';
    }

    function goToReports() {
        if (!selectedStudent) {
            alert('Vui lòng chọn sinh viên trước khi xuất báo cáo.');
            return;
        }
        savePlanDraft();
        exportPrintReport();
    }

    // --- 5. Prerequisite Chain Modal (Chức năng 5) ---
    function escapeAdvisorHtml(value) {
        return String(value ?? '').replace(/[&<>'"]/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[char]));
    }

    // Same prerequisite timeline used by the student experience.
    function renderAdvisorPrerequisiteTimeline(data, container) {
        const target = data.target_course || {};
        const targetCode = target.course_code || '';
        const targetName = target.course_name || targetCode;
        const chain = data.prerequisite_chain || [];
        const styles = {
            completed: { icon: '✅', color: '#059669', bg: '#ecfdf5', border: '#34d399' },
            failed: { icon: '❌', color: '#dc2626', bg: '#fef2f2', border: '#f87171' },
            available: { icon: '⭐', color: '#d97706', bg: '#fffbeb', border: '#fbbf24' },
            locked: { icon: '🔒', color: '#4b5563', bg: '#f3f4f6', border: '#d1d5db' }
        };
        let html = `<div style="margin-bottom:24px;"><h4 style="margin:0 0 12px;color:#111827;font-size:16px;">Mục tiêu: <span style="color:#2563eb;">${escapeAdvisorHtml(targetName)} (${escapeAdvisorHtml(targetCode)})</span></h4><div style="font-size:14px;padding:12px 16px;background:#eff6ff;color:#1d4ed8;border-radius:6px;border-left:4px solid #3b82f6;"><strong>💡 Chỉ dẫn:</strong> ${escapeAdvisorHtml(data.guidance || 'Hoàn thành các học phần theo thứ tự của chuỗi.')}</div></div><div style="position:relative;margin-left:14px;padding-left:24px;border-left:2px solid #e5e7eb;">`;

        if (chain.length === 0) {
            container.innerHTML = html + `<div style="color:#6b7280;font-size:14px;">Học phần này không có môn tiên quyết hoặc sinh viên đã hoàn thành toàn bộ chuỗi.</div></div>`;
            return;
        }

        chain.forEach((item, index) => {
            const state = styles[item.status] || styles.locked;
            const isTarget = item.course_code === targetCode;
            const isCritical = item.course_code === data.critical_course;
            const highlight = isTarget
                ? 'box-shadow:0 0 0 2px #fbbf24,0 8px 16px rgba(245,158,11,.15);border-color:#fbbf24;transform:scale(1.02);z-index:11;'
                : (isCritical ? 'box-shadow:0 0 0 2px #f87171,0 4px 6px -1px rgba(0,0,0,.1);' : '');
            const prerequisites = Array.isArray(item.prerequisites) && item.prerequisites.length
                ? `<div style="font-size:12px;color:#6b7280;margin-top:6px;">Tiên quyết: ${escapeAdvisorHtml(item.prerequisites.join(', '))}</div>` : '';
            html += `<div style="position:relative;margin-bottom:${index === chain.length - 1 ? '0' : '20px'};"><div style="position:absolute;left:-36px;top:12px;width:22px;height:22px;border-radius:50%;background:#fff;border:2px solid ${state.border};display:flex;align-items:center;justify-content:center;font-size:12px;z-index:12;">${state.icon}</div><div style="background:${isTarget ? '#fffbf0' : state.bg};border:1px solid ${state.border};border-radius:8px;padding:12px 16px;transition:all .2s;${highlight}"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;gap:8px;"><strong style="color:${state.color};font-size:15px;">${escapeAdvisorHtml(item.course_name || item.course_code)} (${escapeAdvisorHtml(item.course_code)}) ${isTarget ? '<span style="font-size:11px;padding:3px 8px;border-radius:999px;background:linear-gradient(135deg,#f59e0b,#ea580c);color:#fff;">Mục tiêu</span>' : ''}</strong><span style="font-size:12px;background:#fff;padding:2px 6px;border-radius:4px;border:1px solid #e5e7eb;white-space:nowrap;">${escapeAdvisorHtml(item.credits || 0)} TC</span></div><div style="font-size:13px;color:${state.color};font-weight:500;">Trạng thái: ${escapeAdvisorHtml(item.message || item.status || 'Chưa xác định')}</div>${prerequisites}</div></div>`;
        });
        container.innerHTML = html + '</div>';
    }

    async function openPrereqModal(courseCode) {
        if (!selectedStudent) return;
        const modal = document.getElementById('prereqModal');
        const body = document.getElementById('prereqModalBody');
        if (!modal || !body) return;

        modal.style.display = 'flex';
        body.innerHTML = `<div class="loading-state">⏳ Đang truy vấn cây ontology chuỗi tiên quyết cho học phần ${courseCode}...</div>`;

        try {
            const res = await fetch(`/api/courses/${courseCode}/prerequisite-chain?student_id=${selectedStudent.student_id}`);
            const json = await res.json();
            if (json.success && json.data) {
                renderAdvisorPrerequisiteTimeline(json.data, body);
                return;
                const chain = json.data.prerequisite_chain || [];
                const guidance = json.data.guidance || "Hoàn thành các môn trong chuỗi đúng thứ tự.";
                
                let chainHTML = "";
                if (chain.length === 0) {
                    chainHTML = `<div class="p-3 bg-green-50 text-green-700 rounded-lg">🟢 Học phần này không yêu cầu môn tiên quyết hoặc sinh viên đã hoàn thành toàn bộ chuỗi.</div>`;
                } else {
                    chainHTML = `
                        <div class="p-3 bg-blue-50 text-blue-800 rounded-lg mb-3"><strong>💡 Hướng dẫn học vụ:</strong> ${guidance}</div>
                        <table class="advisor-table table-sm">
                            <thead>
                                <tr><th>Mã học phần</th><th>Tên môn học</th><th>Tình trạng của SV</th></tr>
                            </thead>
                            <tbody>
                                ${chain.map(item => `
                                    <tr>
                                        <td><strong>${item.course_code}</strong></td>
                                        <td>${item.course_name || item.course_code}</td>
                                        <td><span class="badge-status ${item.status === 'Đã hoàn thành' ? 'normal' : 'risk'}">${item.status || 'Chưa đạt'}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                }
                body.innerHTML = chainHTML;
            } else {
                body.innerHTML = `<div class="p-3 bg-red-50 text-red-700 rounded-lg">Không thể phân tích chuỗi tiên quyết: ${json.error || "Lỗi máy chủ"}</div>`;
            }
        } catch (err) {
            console.error("Lỗi lấy chuỗi tiên quyết:", err);
            body.innerHTML = `<div class="p-3 bg-red-50 text-red-700 rounded-lg">Lỗi kết nối máy chủ ontology.</div>`;
        }
    }

    function closePrereqModal() {
        const modal = document.getElementById('prereqModal');
        if (modal) modal.style.display = 'none';
    }

    // --- 6. Plan Confirmation & Consultation Saving (Chức năng 7 & 8) ---
    async function confirmPlan() {
        if (!selectedStudent) {
            alert("Chưa có sinh viên nào được chọn.");
            return;
        }
        if (selectedCourses.size === 0) {
            if (!confirm("Bạn chưa chọn học phần nào cho kế hoạch này. Bạn có chắc muốn chốt kế hoạch rỗng?")) return;
        }

        const notes = (document.getElementById('planConfirmNotes')?.value || "").trim();
        const courses = getActiveRecommendedCourses().filter(course => selectedCourses.has(course.course_code));
        const validation = await validateAdvisorPlanCourses(courses);
        if (!validation.success) {
            alert(`Không thể chốt kế hoạch: ${validation.error}`);
            return;
        }
        const totalCred = Number(validation.data?.total_credits || 0);

        const payload = {
            student_id: selectedStudent.student_id,
            student_name: selectedStudent.name || "",
            notes: notes || "Xác nhận kế hoạch học tập theo gợi ý của Cố vấn học tập.",
            recommended_courses: courses,
            scenario_used: document.getElementById('resScenarioName')?.textContent || currentScenario,
            total_credits: totalCred
        };

        try {
            const res = await fetch('/api/advisor/consultations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (json.success) {
                if (document.getElementById('consultationNotes')) {
                    document.getElementById('consultationNotes').value = notes;
                }
                loadConsultationHistory(selectedStudent.student_id);
                window.UIComponents?.showModalDialog({
                    title: 'Đã xác nhận kế hoạch tư vấn',
                    description: `Kế hoạch của ${selectedStudent.name || selectedStudent.student_id} đã được lưu thành công.`,
                    content: `Đã chốt ${selectedCourses.size} học phần, tổng ${totalCred} tín chỉ. Bạn có thể xuất phiếu tư vấn ngay hoặc ở lại để tiếp tục rà soát.`,
                    actions: [
                        { label: 'Ở lại trang này', variant: 'secondary' },
                        { label: 'Xuất báo cáo tư vấn', onClick: goToReports },
                    ],
                });
            } else {
                alert(`Lỗi khi lưu kế hoạch: ${json.error}`);
            }
        } catch (err) {
            console.error("Lỗi lưu kế hoạch:", err);
            alert("Lỗi kết nối khi gửi dữ liệu xác nhận kế hoạch.");
        }
    }

    async function saveConsultationNote() {
        if (!selectedStudent) {
            alert("Vui lòng chọn sinh viên cần ghi nhận tư vấn.");
            return;
        }
        const notes = (document.getElementById('consultationNotes')?.value || "").trim();
        if (!notes) {
            alert("Vui lòng nhập nội dung nhận xét tư vấn trước khi lưu.");
            return;
        }

        const payload = {
            student_id: selectedStudent.student_id,
            student_name: selectedStudent.name || "",
            notes: notes,
            recommended_courses: getActiveRecommendedCourses().filter(course => selectedCourses.has(course.course_code)),
            scenario_used: "Ghi nhận tư vấn tự do",
            total_credits: parseInt(document.getElementById('liveSelectedCredits')?.textContent || 0)
        };

        try {
            const res = await fetch('/api/advisor/consultations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (json.success) {
                alert("💾 Đã lưu hồ sơ nhận xét tư vấn thành công.");
                document.getElementById('consultationNotes').value = "";
                loadConsultationHistory(selectedStudent.student_id);
            } else {
                alert(`Lỗi lưu nhận xét: ${json.error}`);
            }
        } catch (err) {
            console.error("Lỗi lưu nhận xét:", err);
            alert("Lỗi kết nối khi lưu nhận xét tư vấn.");
        }
    }

    async function loadConsultationHistory(studentId) {
        const container = document.getElementById('historyListContainer');
        if (!container) return;

        try {
            const res = await fetch(`/api/advisor/consultations/${studentId}`);
            const json = await res.json();
            if (json.success && Array.isArray(json.data) && json.data.length > 0) {
                container.innerHTML = json.data.map(item => `
                    <div class="history-item">
                        <div class="history-item__top">
                            <span>📌 ${item.scenario_used || "Tư vấn KHHT"} (${item.total_credits || 0} TC)</span>
                            <small class="text-gray">${item.created_at || ""}</small>
                        </div>
                        <div class="text-sm text-gray">CVHT: <strong>${item.advisor_name || "Hệ thống"}</strong></div>
                        <div class="history-item__notes">${item.notes || "Không có ghi chú thêm."}</div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = `<p class="text-gray text-sm">Chưa có bản ghi tư vấn nào cho sinh viên này.</p>`;
            }
        } catch (err) {
            console.error("Lỗi tải lịch sử tư vấn:", err);
        }
    }

    function getOrCreatePrintContainer() {
        let container = document.getElementById('printReportContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'printReportContainer';
            container.className = 'print-only';
            document.body.appendChild(container);
        }
        return container;
    }

    // --- In Hồ sơ / In Kế hoạch học tập (Tham khảo UI sinh viên) ---
    function getSemesterLabel(semesterTaken) {
        const semester = Number(semesterTaken);
        if (semester === 1) return "Học kỳ 1";
        if (semester === 2) return "Học kỳ 2";
        if (semester === 3) return "Học kỳ 3";
        return "Chưa xác định";
    }

    const NON_ACCUMULATED_ENGLISH_COURSES = new Set(['FLS310', 'FLS312', 'FLS313']);
    const NON_ACCUMULATED_FIXED_COURSES = new Set(['SOT301']);
    
    function isNonAccumulatedCourse(code, name = '') {
        const normalizedCode = String(code || '').trim().toUpperCase();
        const normalizedName = String(name || '').trim().toLowerCase();
        return NON_ACCUMULATED_ENGLISH_COURSES.has(normalizedCode)
            || NON_ACCUMULATED_FIXED_COURSES.has(normalizedCode)
            || normalizedName.includes('giáo dục thể chất');
    }

    function formatGradeDisplay(attempt) {
        if (attempt.status === "Không tính điểm" || attempt.status === "Miễn") {
            return attempt.status;
        }
        if (attempt.status === "Đạt" && (attempt.grade === 0 || attempt.grade === 0.0 || attempt.grade === "0" || attempt.grade === "0.0" || attempt.grade_specified === false || attempt.grade === undefined || attempt.grade === null)) {
            return "Điểm đạt";
        }
        if (attempt.grade !== undefined && attempt.grade !== null && attempt.grade !== "") {
            const num = Number(attempt.grade);
            return isNaN(num) ? "0.0" : num.toFixed(1);
        }
        return attempt.status || "-";
    }

    function calculateAcademicMetrics(attempts) {
        const courseSummaryMap = {};
        
        attempts.forEach(attempt => {
            const key = attempt.code || attempt.course_code;
            if (!key) return;
            
            if (!courseSummaryMap[key]) {
                const courseInfo = courseMap.get(key);
                courseSummaryMap[key] = {
                    code: key,
                    name: attempt.name || attempt.course_name,
                    hasPassed: false,
                    bestGrade: null,
                    credits: courseInfo ? Number(courseInfo.credits || 0) : 0,
                    gradeSpecified: false
                };
            }
            
            const entry = courseSummaryMap[key];
            const isPassed = ["Đạt", "Miễn", "Không tính điểm"].includes(attempt.status);
            
            if (isPassed) {
                entry.hasPassed = true;
                if (attempt.grade_specified && attempt.status === "Đạt") {
                    const g = parseFloat(attempt.grade);
                    if (!isNaN(g) && (entry.bestGrade === null || g > entry.bestGrade)) {
                        entry.bestGrade = g;
                        entry.gradeSpecified = true;
                    }
                }
            }
        });

        const uniqueCourses = Object.values(courseSummaryMap);
        const passedCourses = uniqueCourses.filter(c => c.hasPassed);
        
        const accumulatedCredits = passedCourses.reduce((sum, c) => {
            if (isNonAccumulatedCourse(c.code, c.name)) return sum;
            return sum + (c.credits || 0);
        }, 0);

        let totalGradePoints = 0;
        let totalCreditsForGpa = 0;
        
        passedCourses.forEach(c => {
            if (isNonAccumulatedCourse(c.code, c.name)) return;
            
            if (c.gradeSpecified && c.bestGrade !== null) {
                const credits = c.credits || 0;
                if (credits > 0) {
                    totalGradePoints += c.bestGrade * credits;
                    totalCreditsForGpa += credits;
                }
            }
        });

        const gpa = totalCreditsForGpa > 0 ? (totalGradePoints / totalCreditsForGpa).toFixed(2) : "0.00";
        return { totalCredits: accumulatedCredits, gpa };
    }

    function printStudentProfile() {
        if (!selectedStudent) {
            alert("Vui lòng chọn một sinh viên để in hồ sơ học tập.");
            return;
        }
        
        const s = selectedStudent;
        const attempts = (s.course_attempts || []).map(a => ({
            ...a,
            code: a.course_code,
            name: a.course_name
        }));
        
        const metrics = calculateAcademicMetrics(attempts);
        const container = getOrCreatePrintContainer();
        
        const studentName = s.name || "";
        const major = s.major || "";
        const academicClass = s.academic_class || "";
        const studentIdToDisplay = s.student_id || "";
        const yearAdmitted = s.year_admitted || "";
        
        const groups = new Map();
        attempts.forEach(attempt => {
            const actualTerm = Number(attempt.actual_term || 0);
            const semesterTaken = Number(attempt.semester_taken || 0);
            const academicYear = attempt.academic_year || "";
            const groupKey = `${actualTerm}|${semesterTaken}|${academicYear}`;
            if (!groups.has(groupKey)) {
                groups.set(groupKey, {
                    semesterTaken,
                    academicYear,
                    actualTerm,
                    items: []
                });
            }
            groups.get(groupKey).items.push(attempt);
        });
        const sortedGroups = Array.from(groups.values()).sort((a, b) => {
            return (Number(a.actualTerm) || 0) - (Number(b.actualTerm) || 0);
        });

        let tableHtml = `
            <table class="print-table">
                <thead>
                    <tr>
                        <th>Mã MH</th>
                        <th>Tên môn học</th>
                        <th>TC</th>
                        <th>Kết quả</th>
                    </tr>
                </thead>
                <tbody>
        `;

        sortedGroups.forEach(group => {
            const groupMetrics = calculateAcademicMetrics(group.items);
            tableHtml += `
                <tr class="print-group-header">
                    <td colspan="4" style="text-align: left;">${getSemesterLabel(group.semesterTaken)} năm học ${group.academicYear || "-"}</td>
                </tr>
            `;
            
            group.items
                .sort((a, b) => {
                    const termDiff = Number(a.actual_term || 0) - Number(b.actual_term || 0);
                    if (termDiff !== 0) return termDiff;
                    const attemptDiff = Number(a.attempt_number || 1) - Number(b.attempt_number || 1);
                    if (attemptDiff !== 0) return attemptDiff;
                    return String(a.code || "").localeCompare(String(b.code || ""));
                })
                .forEach(attempt => {
                    const courseInfo = courseMap.get(attempt.code);
                    const credits = courseInfo ? courseInfo.credits : "";
                    const gradeToDisplay = formatGradeDisplay(attempt);
                    
                    tableHtml += `
                        <tr>
                            <td class="text-center">${escapeHtml(attempt.code)}</td>
                            <td>${escapeHtml(attempt.name)}</td>
                            <td class="text-center">${escapeHtml(String(credits))}</td>
                            <td class="text-center">${escapeHtml(gradeToDisplay)}</td>
                        </tr>
                    `;
                });
                
            tableHtml += `
                <tr class="print-group-footer">
                    <td colspan="3" style="text-align: left;"><strong>Số tín chỉ tích lũy:</strong></td>
                    <td class="text-center"><strong>${groupMetrics.totalCredits}</strong></td>
                </tr>
                <tr class="print-group-footer">
                    <td colspan="3" style="text-align: left;"><strong>ĐVHT TL/ĐTB TL cộng/ĐTB HK:</strong></td>
                    <td class="text-center"><strong>${groupMetrics.totalCredits} | ${groupMetrics.gpa} | ${groupMetrics.gpa}</strong></td>
                </tr>
            `;
        });
        
        const today = new Date();
        const dateString = `Khánh Hòa, ngày ${today.getDate().toString().padStart(2, '0')} tháng ${(today.getMonth() + 1).toString().padStart(2, '0')} năm ${today.getFullYear()}`;
        
        tableHtml += `
            </tbody>
            </table>
            
            <div class="print-signature">
                <div class="print-signature-box">
                    <div><i>${dateString}</i></div>
                    <div class="print-sig-title">TL.HIỆU TRƯỞNG</div>
                    <div class="print-sig-title">TRƯỞNG PHÒNG ĐÀO TẠO</div>
                </div>
            </div>
        `;
        
        container.innerHTML = `
            <div class="print-table-wrapper">
                <div class="print-header">
                    <div class="print-header-left">
                        <div class="print-university">TRƯỜNG ĐẠI HỌC NHA TRANG</div>
                        <div class="print-department">PHÒNG ĐÀO TẠO ĐẠI HỌC</div>
                    </div>
                    <div class="print-header-right">
                        <div class="print-title">BẢNG ĐIỂM HỌC KỲ</div>
                    </div>
                </div>
                
                <div class="print-student-info">
                    <div class="print-info-row">
                        Họ tên: <strong>${escapeHtml(studentName)} - ${escapeHtml(academicClass)} - ${escapeHtml(studentIdToDisplay)}</strong>
                    </div>
                    <div class="print-info-row">
                        Ngành: <strong>Đại học chính quy - ${escapeHtml(major)}</strong>
                    </div>
                    <div class="print-info-row">
                        Điểm TB tích lũy: <strong>${metrics.gpa}</strong> ĐVHT Tích lũy(TC): <strong>${metrics.totalCredits}</strong>
                    </div>
                </div>
                
                ${tableHtml}
            </div>
        `;
        window.print();
    }

    function printStudentPlan() {
        if (!selectedStudent) {
            alert("Vui lòng chọn một sinh viên để in kế hoạch học tập.");
            return;
        }
        let list = getActiveRecommendedCourses();
        if (selectedCourses.size > 0) {
            list = list.filter(course => selectedCourses.has(course.course_code));
        }

        if (!list || list.length === 0) {
            alert("Chưa có danh sách môn học đề xuất cho sinh viên này. Vui lòng sang 'Gợi ý Kế hoạch' chạy thuật toán trước khi in!");
            return;
        }

        const container = getOrCreatePrintContainer();
        const s = selectedStudent;
        const gpa = parseFloat(s.gpa_accumulated || 0).toFixed(2);
        const dateStr = new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
        
        let totalCredits = 0;
        const coursesRows = list.map((c, i) => {
            const cred = Number(c.credits || 0);
            totalCredits += cred;
            return `
                <tr>
                    <td style="text-align: center; padding: 8px;">${i + 1}</td>
                    <td style="padding: 8px;"><strong>${escapeHtml(c.course_code || "-")}</strong></td>
                    <td style="padding: 8px;">${escapeHtml(c.course_name || c.course_code || "-")}</td>
                    <td style="text-align: center; padding: 8px;"><strong>${cred}</strong></td>
                    <td style="padding: 8px;">${escapeHtml(c.course_type || "Bắt buộc")}</td>
                    <td style="padding: 8px;">${escapeHtml(c.reason || "Đạt điều kiện tiên quyết")}</td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <div class="print-header" style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 20px;">
                <h3 style="margin: 0; font-size: 16px; font-weight: normal;">TRƯỜNG ĐẠI HỌC NHA TRANG • PHÒNG ĐÀO TẠO ĐẠI HỌC</h3>
                <h1 style="margin: 10px 0 5px; font-size: 22px; font-weight: bold;">KẾ HOẠCH VÀ LỘ TRÌNH HỌC TẬP ĐỀ XUẤT</h1>
                <p style="margin: 0; font-style: italic; font-size: 13px;">Học kỳ tư vấn • Ngày lập: ${dateStr}</p>
            </div>

            <div style="margin-top: 16px; line-height: 1.8; font-size: 14px; border: 1px solid #ddd; padding: 12px 16px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                    <span><strong>Mã sinh viên:</strong> ${escapeHtml(s.student_id || "-")}</span>
                    <span><strong>Họ và tên:</strong> ${escapeHtml(s.name || "-")}</span>
                    <span><strong>Lớp hành chính:</strong> ${escapeHtml(s.academic_class || "-")}</span>
                </div>
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap; margin-top: 4px;">
                    <span><strong>Ngành:</strong> ${escapeHtml(s.major || "CNTT")}</span>
                    <span><strong>Chuyên ngành:</strong> ${escapeHtml(s.specialization || "Chưa chọn")}</span>
                    <span><strong>GPA tích lũy:</strong> <strong>${gpa}</strong></span>
                </div>
            </div>

            <div style="margin: 16px 0 8px; display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; font-size: 16px;">DANH SÁCH MÔN HỌC ĐỀ XUẤT CHO HỌC KỲ TỚI</h3>
                <span style="font-size: 14px;">Tổng môn: <strong>${list.length}</strong> • Tổng tín chỉ: <strong style="font-size: 16px;">${totalCredits} TC</strong></span>
            </div>
            <table class="print-table" style="width: 100%; border-collapse: collapse; font-size: 13px;" border="1">
                <thead>
                    <tr style="background: #f0f0f0;">
                        <th width="40" style="text-align: center; padding: 8px;">STT</th>
                        <th width="90" style="padding: 8px;">Mã môn</th>
                        <th style="padding: 8px;">Tên học phần</th>
                        <th width="50" style="text-align: center; padding: 8px;">TC</th>
                        <th width="80" style="padding: 8px;">Nhóm</th>
                        <th style="padding: 8px;">Lý do hệ thống chọn</th>
                    </tr>
                </thead>
                <tbody>
                    ${coursesRows}
                </tbody>
            </table>

            <div style="display: flex; justify-content: space-between; margin-top: 40px; padding: 0 30px; text-align: center; font-size: 14px;">
                <div>
                    <p style="margin: 0; font-weight: bold;">SINH VIÊN ĐĂNG KÝ / XÁC NHẬN</p>
                    <p style="margin: 4px 0 0; font-style: italic; font-size: 12px;">(Ký và ghi rõ họ tên)</p>
                    <div style="height: 60px;"></div>
                    <p style="margin: 0; font-weight: bold;">${escapeHtml(s.name || "-")}</p>
                </div>
                <div>
                    <p style="margin: 0; font-style: italic; font-size: 12px;">Khánh Hòa, ${dateStr}</p>
                    <p style="margin: 4px 0 0; font-weight: bold;">CỐ VẤN HỌC TẬP PHÊ DUYỆT</p>
                    <div style="height: 60px;"></div>
                    <p style="margin: 0; font-weight: bold;">${escapeHtml(sessionStorage.getItem("advisorName") || "Trần Thị A")}</p>
                </div>
            </div>
        `;
        window.print();
    }

    // --- 7. Export Printable Report (Chức năng 9) ---
    function exportPrintReport() {
        if (!selectedStudent) {
            alert("Vui lòng chọn một sinh viên để xuất báo cáo tư vấn.");
            return;
        }

        const container = getOrCreatePrintContainer();

        const s = selectedStudent;
        const gpa = parseFloat(s.gpa_accumulated || 0).toFixed(2);
        const dateStr = new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const notes = (document.getElementById('consultationNotes')?.value || "").trim() || "Xác nhận kế hoạch học tập theo gợi ý từ thuật toán ontology.";

        let coursesRows = "";
        if (selectedCourses.size > 0 && recommendationData) {
            let list = [];
            if (Array.isArray(recommendationData.plans)) {
                list = recommendationData.plans[currentCompareIndex]?.recommended_courses || [];
            } else {
                list = recommendationData.recommended_courses || [];
            }
            list.filter(c => selectedCourses.has(c.course_code)).forEach((c, i) => {
                coursesRows += `
                    <tr>
                        <td>${i + 1}</td>
                        <td><strong>${c.course_code}</strong></td>
                        <td>${c.course_name || c.course_code}</td>
                        <td>${c.credits || 0}</td>
                        <td>${c.reason || "-"}</td>
                    </tr>
                `;
            });
        } else {
            coursesRows = `<tr><td colspan="5" style="text-align: center;">Chưa chọn học phần nào trong kế hoạch</td></tr>`;
        }

        container.innerHTML = `
            <div class="print-header">
                <h2 style="margin: 0;">BỘ GIÁO DỤC VÀ ĐÀO TẠO • TRƯỜNG ĐẠI HỌC NHA TRANG</h2>
                <h1 style="margin: 10px 0 5px; font-size: 20px;">PHIẾU TƯ VẤN & XÁC NHẬN KẾ HOẠCH HỌC TẬP</h1>
                <p style="margin: 0; font-style: italic;">Ngày lập phiếu: ${dateStr}</p>
            </div>

            <div style="margin-top: 20px; line-height: 1.6;">
                <p><strong>Mã sinh viên:</strong> ${s.student_id} &nbsp;&nbsp;&nbsp;&nbsp; <strong>Họ và tên:</strong> ${s.name || "-"}</p>
                <p><strong>Lớp hành chính:</strong> ${s.academic_class || "-"} &nbsp;&nbsp;&nbsp;&nbsp; <strong>Chuyên ngành:</strong> ${s.specialization || "Chưa chọn"}</p>
                <p><strong>Điểm TB tích lũy (GPA):</strong> ${gpa} &nbsp;&nbsp;&nbsp;&nbsp; <strong>Tín chỉ tích lũy:</strong> ${s.total_credits_accumulated || 0} TC</p>
                <p><strong>Cố vấn học tập phụ trách:</strong> ${sessionStorage.getItem("advisorName") || "Trần Thị A"}</p>
            </div>

            <h3 style="margin: 25px 0 10px; font-size: 16px;">1. DANH SÁCH HỌC PHẦN ĐƯỢC THỐNG NHẤT TƯ VẤN</h3>
            <table class="print-table">
                <thead>
                    <tr style="background: #f0f0f0;">
                        <th width="40">STT</th>
                        <th width="100">Mã môn</th>
                        <th>Tên học phần</th>
                        <th width="70">Tín chỉ</th>
                        <th>Ghi chú / Lý do</th>
                    </tr>
                </thead>
                <tbody>
                    ${coursesRows}
                </tbody>
            </table>

            <h3 style="margin: 25px 0 10px; font-size: 16px;">2. NHẬN XÉT VÀ ĐỊNH HƯỚNG CỦA CỐ VẤN HỌC TẬP</h3>
            <div style="border: 1px solid #000; padding: 15px; min-height: 80px; border-radius: 4px;">
                ${notes}
            </div>

            <div class="print-signatures">
                <div style="text-align: center;">
                    <p><strong>SINH VIÊN</strong></p>
                    <p style="font-style: italic; font-size: 13px;">(Ký và ghi rõ họ tên)</p>
                    <br><br><br>
                    <p>${s.name || "-"}</p>
                </div>
                <div style="text-align: center;">
                    <p><strong>CỐ VẤN HỌC TẬP</strong></p>
                    <p style="font-style: italic; font-size: 13px;">(Ký và ghi rõ họ tên)</p>
                    <br><br><br>
                    <p>${document.querySelector('.workspace-hero strong')?.textContent || "Cố vấn học tập"}</p>
                </div>
            </div>
        `;

        window.print();
    }

    // --- 8. System Evaluations (Chức năng 9) ---
    function initStarRatings() {
        ['ratingAccuracy', 'ratingUsefulness'].forEach(id => {
            const container = document.getElementById(id);
            if (!container) return;
            const stars = container.querySelectorAll('.star');
            stars.forEach(s => {
                s.addEventListener('click', () => {
                    const val = parseInt(s.dataset.val);
                    stars.forEach(st => {
                        st.classList.toggle('active', parseInt(st.dataset.val) <= val);
                    });
                });
            });
        });
    }

    function getRatingValue(id) {
        const container = document.getElementById(id);
        if (!container) return 5;
        const activeStars = container.querySelectorAll('.star.active');
        return activeStars.length || 5;
    }

    async function submitEvaluation() {
        const acc = getRatingValue('ratingAccuracy');
        const use = getRatingValue('ratingUsefulness');
        const comm = (document.getElementById('evalComments')?.value || "").trim();

        const payload = {
            accuracy_rating: acc,
            usefulness_rating: use,
            comments: comm
        };

        try {
            const res = await fetch('/api/advisor/evaluations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (json.success) {
                if (document.getElementById('evalComments')) document.getElementById('evalComments').value = "";
                loadCommunityEvaluations();
                window.UIComponents?.showModalDialog({
                    title: 'Cảm ơn đánh giá của bạn',
                    description: json.message || 'Đánh giá về hệ thống đã được ghi nhận thành công.',
                    content: `Tính chính xác: ${acc}/5 sao · Tính hữu ích: ${use}/5 sao`,
                    actions: [{ label: 'Đóng', variant: 'secondary' }],
                });
            } else {
                alert(`Lỗi gửi đánh giá: ${json.error}`);
            }
        } catch (err) {
            console.error("Lỗi gửi đánh giá:", err);
            alert("Lỗi kết nối khi gửi đánh giá hệ thống.");
        }
    }

    async function loadCommunityEvaluations() {
        const container = document.getElementById('evalListContainer');
        if (!container) return;

        try {
            const res = await fetch('/api/advisor/evaluations');
            const json = await res.json();
            if (json.success && Array.isArray(json.data) && json.data.length > 0) {
                container.innerHTML = json.data.slice(0, 5).map(item => `
                    <div class="eval-item">
                        <div class="eval-item__top">
                            <span>⭐ Chính xác: ${item.accuracy_rating}/5 | Hữu ích: ${item.usefulness_rating}/5</span>
                            <small class="text-gray">${item.created_at || ""}</small>
                        </div>
                        <div class="text-sm text-gray">Giảng viên: <strong>${item.advisor_name || "CVHT"}</strong></div>
                        ${item.comments ? `<div class="eval-item__comment">${item.comments}</div>` : ''}
                    </div>
                `).join('');
            } else {
                container.innerHTML = `<p class="text-gray text-sm">Chưa có ý kiến phản hồi nào được ghi nhận.</p>`;
            }
        } catch (err) {
            console.error("Lỗi tải đánh giá cộng đồng:", err);
        }
    }

    // --- 10. Add / Update Student Profile (Redirects to standalone editor page) ---
    function openAddStudentModal(targetId = "") {
        if (targetId && typeof targetId === 'string') {
            window.location.href = `/advisor/student-editor?id=${encodeURIComponent(targetId)}`;
        } else {
            window.location.href = `/advisor/student-editor`;
        }
    }

    // Public API
    return {
        init,
        switchSubTab,
        applyFilters,
        resetFilters,
        deleteStudent,
        selectStudent,
        selectScenario,
        runRecommendation,
        goToConsultation,
        goToScenarios,
        goToReports,
        openAddCourseModal,
        addCourseToPlan,
        editPlanCourseReason,
        removeCourseFromPlan,
        switchComparePlan,
        toggleExcludedPanel,
        showExcludedCoursesByRule,
        toggleExcludedCoursesDetail,
        updateSelectedLiveStats,
        openPrereqModal,
        closePrereqModal,
        confirmPlan,
        saveConsultationNote,
        exportPrintReport,
        printStudentProfile,
        printStudentPlan,
        submitEvaluation,
        openAddStudentModal
    };
})();

document.addEventListener("DOMContentLoaded", () => {
    AdvisorWorkspace.init();
});
