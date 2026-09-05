// ========== SESSION STORAGE KEY ==========
    const SESSION_KEY = 'studentPageState';

    // Đặt vào window để main.js nhận biết và không chạy logic load đè
    window.currentStudent = null; 
    currentRecommendation = null;

    // ========== LƯU / KHÔI PHỤC STATE ==========
    function saveState(shouldRestore = false) {
        try {
            const state = {
                searchTerm: document.getElementById('studentSearch').value,
                classFilterValue: document.getElementById('classFilterSelect').value,
                selectValue: document.getElementById('studentSelect').value,
                currentStudent: window.currentStudent,
                currentRecommendation: currentRecommendation,
                showProfile: document.getElementById('studentProfileSection').style.display !== 'none',
                showAction: document.getElementById('recommendationActionSection').style.display !== 'none',
                showResults: document.getElementById('resultsSection').style.display !== 'none'
            };
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
            if (shouldRestore) {
                sessionStorage.setItem('shouldRestore', 'true');
            }
            console.log("Đã lưu trạng thái. Có cần khôi phục:", shouldRestore);
        } catch (e) { console.error("Lỗi lưu trạng thái:", e); }
    }

    function restoreState() {
        try {
            // Chỉ khôi phục nếu có cờ 'shouldRestore'
            const shouldRestore = sessionStorage.getItem('shouldRestore') === 'true';
            if (!shouldRestore) {
                sessionStorage.removeItem(SESSION_KEY);
                return false;
            }

            const raw = sessionStorage.getItem(SESSION_KEY);
            if (!raw) return false;
            
            const state = JSON.parse(raw);
            console.log("Đang khôi phục trạng thái...");

            // Khôi phục ô tìm kiếm
            if (state.searchTerm) {
                document.getElementById('studentSearch').value = state.searchTerm;
            }

            // Khôi phục bộ lọc lớp hành chính
            if (state.classFilterValue) {
                document.getElementById('classFilterSelect').value = state.classFilterValue;
                filterStudentsByClass();
            }

            // Khôi phục dữ liệu sinh viên
            if (state.currentStudent) {
                loadStudent(state.currentStudent.student_id);

                // Đồng bộ dropdown sau khi profile đã được hiển thị
                const sel = document.getElementById('studentSelect');
                if (state.selectValue) sel.value = state.selectValue;
            }

            // Khôi phục kết quả gợi ý nếu có
            if (state.currentRecommendation) {
                currentRecommendation = state.currentRecommendation;
                displayRecommendationResults(currentRecommendation);
            }

            // Điều chỉnh hiển thị section
            document.getElementById('studentProfileSection').style.display = state.showProfile ? 'block' : 'none';
            document.getElementById('recommendationActionSection').style.display = state.showAction ? 'block' : 'none';
            document.getElementById('resultsSection').style.display = state.showResults ? 'block' : 'none';

            // Xóa cờ sau khi đã dùng
            sessionStorage.removeItem('shouldRestore');
            return true;
        } catch (e) {
            console.error("Lỗi khôi phục trạng thái:", e);
            sessionStorage.removeItem(SESSION_KEY);
            return false;
        }
    }

    // Tải danh sách sinh viên khi trang được mở
    document.addEventListener('DOMContentLoaded', async function () {
        const content = document.getElementById('mainStudentsContent');
        try {
            // Chờ tải xong danh sách sinh viên mới khôi phục state đầy đủ
            await loadStudentList();
            restoreState();
        } finally {
            // Hiện trang sau khi đã load xong mọi thứ để tránh nháy
            if (content) content.style.opacity = '1';
        }

        // Auto-search với debounce khi người dùng gõ mã sinh viên
        let searchDebounceTimer = null;
        const searchInput = document.getElementById('studentSearch');

        searchInput.addEventListener('input', function () {
            clearTimeout(searchDebounceTimer);
            if (!this.value.trim()) return;
            searchDebounceTimer = setTimeout(searchStudent, 400);
        });

        // Vẫn hỗ trợ nhấn Enter
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                clearTimeout(searchDebounceTimer);
                searchStudent();
            }
        });
    });

    // Đổ danh sách sinh viên vào ô chọn (Async)
    async function loadStudentList() {
        try {
            const response = await fetch('/api/students');
            const data = await response.json();
            allStudents = data.data || [];

            // Tải danh sách lớp hành chính
            await loadAcademicClassesList();

            // Ban đầu chưa chọn lớp -> hiển thị trống/disabled cho ô chọn sinh viên
            const select = document.getElementById('studentSelect');
            select.innerHTML = '<option value="">-- Vui lòng chọn lớp hành chính trước --</option>';
            select.disabled = true;
            return true;
        } catch (error) {
            showError('Lỗi tải danh sách sinh viên: ' + error, 'error');
            console.error('Lỗi:', error);
            return false;
        }
    }

    // Tải danh sách lớp hành chính từ server
    async function loadAcademicClassesList() {
        try {
            const response = await fetch('/api/students/academic-classes');
            const data = await response.json();
            const classSelect = document.getElementById('classFilterSelect');
            const classes = data.data || [];
            
            classSelect.innerHTML = '<option value="">-- Chọn lớp hành chính --</option>';
            classes.forEach(cls => {
                const option = document.createElement('option');
                option.value = cls;
                option.textContent = cls;
                classSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Lỗi tải danh sách lớp hành chính:', error);
        }
    }

    // Lọc sinh viên theo lớp hành chính đã chọn
    function filterStudentsByClass() {
        const selectedClass = document.getElementById('classFilterSelect').value;
        const select = document.getElementById('studentSelect');
        
        if (!selectedClass) {
            select.innerHTML = '<option value="">-- Vui lòng chọn lớp hành chính trước --</option>';
            select.disabled = true;
            return;
        }
        
        select.disabled = false;
        const filtered = allStudents.filter(s => s.academic_class === selectedClass);
        renderStudentOptions(filtered);
    }

    // Render danh sách sinh viên vào select element
    function renderStudentOptions(students) {
        const select = document.getElementById('studentSelect');
        select.innerHTML = '<option value="">-- Chọn sinh viên --</option>';
        students.forEach(student => {
            const option = document.createElement('option');
            option.value = student.student_id;
            option.textContent = `${student.student_id} - ${student.name}`;
            select.appendChild(option);
        });
    }

    // Tìm sinh viên theo mã
    function searchStudent() {
        const studentId = document.getElementById('studentSearch').value.trim();
        if (!studentId) return;
        loadStudent(studentId);
    }

    // Xử lý khi chọn sinh viên từ ô chọn
    function onStudentSelected() {
        const studentId = document.getElementById('studentSelect').value;
        if (studentId) {
            loadStudent(studentId);
        }
    }

    // Tải hồ sơ sinh viên
    function loadStudent(studentId) {
        fetch(`/api/students/${studentId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.currentStudent = data.data;
                    displayStudentProfile(window.currentStudent);
                    hideError();
                    fetchEligibleCourses(studentId);
                } else {
                    showError(data.error || 'Không tìm thấy sinh viên', 'warning');
                }
            })
            .catch(error => {
                showError('Lỗi tải thông tin sinh viên: ' + error, 'error');
                console.error('Lỗi:', error);
            });
    }

    // Tải danh sách môn đủ điều kiện học (gọi API recommendations)
    async function fetchEligibleCourses(studentId) {
        const eligibleSpinner = document.getElementById('eligibleLoadingSpinner');
        const eligibleSection = document.getElementById('eligibleCoursesSection');
        const generateBtn = document.getElementById('generateBtn');
        const resultsSection = document.getElementById('resultsSection');

        if (eligibleSpinner) eligibleSpinner.style.display = 'block';
        if (eligibleSection) eligibleSection.style.display = 'none';
        if (generateBtn) {
            generateBtn.disabled = true;
        }
        if (resultsSection) resultsSection.style.display = 'none';

        try {
            const response = await fetch('/api/recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    student_id: studentId
                })
            });
            const data = await response.json();
            if (eligibleSpinner) eligibleSpinner.style.display = 'none';

            if (data.success) {
                currentRecommendation = data.data;
                displayEligibleCourses(currentRecommendation.eligible_courses || []);
                displayExcludedCourses(currentRecommendation.excluded_courses || []);
                if (eligibleSection) eligibleSection.style.display = 'block';
                if (generateBtn) {
                    generateBtn.disabled = false;
                }
                hideError();
                saveState();
            } else {
                showError(data.error || 'Lỗi tải danh sách môn đủ điều kiện', 'error');
            }
        } catch (error) {
            if (eligibleSpinner) eligibleSpinner.style.display = 'none';
            showError('Lỗi tải danh sách môn đủ điều kiện: ' + error, 'error');
            console.error('Lỗi:', error);
        }
    }

    // Hiển thị hồ sơ sinh viên
    function displayStudentProfile(student) {
        if (!student) return;

        // Cập nhật các trường text
        const mapping = {
            'profileStudentId': student.student_id,
            'profileName': student.name,
            'profileMajor': student.major || '-',
            'profileSpecialization': student.specialization || 'Chưa chọn',
            'profileGoal': student.study_goal || '-',
            'profileSemester': student.current_semester,
            'profileCredits': student.total_credits_accumulated,
            'profileGPA': student.gpa_accumulated !== undefined ? Number(student.gpa_accumulated).toFixed(2) : '0.00',
            'profileAcademicClass': student.academic_class || 'Chưa xếp lớp',
            'profileYearAdmitted': student.year_admitted || '-'
        };

        for (const [id, value] of Object.entries(mapping)) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }

        // Hiển thị môn đã học
        const passedList = student.passed_courses || [];
        document.getElementById('passedCoursesCount').textContent = `${passedList.length} môn`;
        document.getElementById('passedCoursesList').innerHTML = passedList.slice(0, 15)
            .map(c => `<span class="course-badge">${c}</span>`)
            .join('') + (passedList.length > 15 ? ' <span class="more">...</span>' : '');

        // Hiển thị môn chưa đạt
        const failedList = student.failed_courses || [];
        document.getElementById('failedCoursesCount').textContent = `${failedList.length} môn`;
        document.getElementById('failedCoursesList').innerHTML = failedList
            .map(c => `<span class="course-badge failed">${c}</span>`)
            .join('');

        // Hiển thị các khu vực
        document.getElementById('studentProfileSection').style.display = 'block';
        document.getElementById('recommendationActionSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';
        
        // Ẩn danh sách môn đủ điều kiện của sinh viên trước đó (nếu có)
        const eligibleSection = document.getElementById('eligibleCoursesSection');
        if (eligibleSection) eligibleSection.style.display = 'none';
        
        // Luôn lưu lại state khi profile thay đổi
        saveState();
    }

    function openCourseHistory() {
        const studentIdFromInline = window.currentStudent && window.currentStudent.student_id ? window.currentStudent.student_id : '';
        const studentIdFromMainJs = window.selectedStudent && window.selectedStudent.student_id ? window.selectedStudent.student_id : '';
        const studentIdFromSelect = (document.getElementById('studentSelect') || {}).value || '';
        const studentIdFromSearch = ((document.getElementById('studentSearch') || {}).value || '').trim();

        const studentId = (studentIdFromInline || studentIdFromMainJs || studentIdFromSelect || studentIdFromSearch || '').trim();

        if (!studentId) {
            showError('Vui lòng chọn hoặc nhập mã sinh viên trước khi xem chi tiết danh sách', 'warning');
            return;
        }

        // Lưu state trước khi điều hướng để khôi phục khi quay lại
        saveState(true);
        window.location.href = `/students/${encodeURIComponent(studentId)}/course-history`;
     }

    function confirmDeleteStudent() {
        const student = window.currentStudent || window.selectedStudent;
        if (!student || !student.student_id) {
            showError('Không tìm thấy thông tin sinh viên để xóa', 'warning');
            return;
        }

        const confirmMsg = `Bạn có chắc chắn muốn xóa sinh viên ${student.name} (${student.student_id}) không? Hành động này không thể hoàn tác.`;
        if (confirm(confirmMsg)) {
            deleteStudent(student.student_id);
        }
    }

    async function deleteStudent(studentId) {
        try {
            const response = await fetch(`/api/students/${studentId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            const data = await response.json();
            if (data.success) {
                showToast(data.message || `Đã xóa sinh viên ${studentId} thành công`, 'success');
                resetForm();
                await loadStudentList();
            } else {
                showError(data.error || 'Có lỗi xảy ra khi xóa sinh viên', 'error');
            }
        } catch (error) {
            showError('Lỗi kết nối khi xóa sinh viên: ' + error, 'error');
            console.error('Lỗi:', error);
        }
    }

    // Tạo gợi ý kế hoạch học tập
    function generateRecommendation() {
        if (!currentRecommendation) {
            showError('Không có dữ liệu gợi ý sẵn sàng', 'warning');
            return;
        }

        const spinner = document.getElementById('loadingSpinner');
        const generateBtn = document.getElementById('generateBtn');

        if (spinner) spinner.style.display = 'block';
        if (generateBtn) generateBtn.disabled = true;

        // Cho một khoảng trễ cực nhỏ để tạo cảm giác xử lý mượt mà trên UI trước khi hiển thị kết quả tức thì
        setTimeout(() => {
            if (spinner) spinner.style.display = 'none';
            if (generateBtn) generateBtn.disabled = false;
            displayRecommendationResults(currentRecommendation);
            
            // Cuộn mượt đến phần kết quả gợi ý
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }
        }, 100);
    }

    // Hiển thị kết quả gợi ý
    function displayRecommendationResults(result) {
        // Tóm tắt
        document.getElementById('resultTotalCourses').textContent = result.recommended_courses?.length || 0;
        document.getElementById('resultTotalCredits').textContent = result.total_recommended_credits || 0;
        document.getElementById('resultNextSemester').textContent = result.next_semester || '-';

        displayEligibleCourses(result.eligible_courses || []);
        displayExcludedCourses(result.excluded_courses || []);
        displayResultWarnings(result);
        displayResultInsights(result);

        // Bảng danh sách môn được gợi ý
        const coursesList = document.getElementById('recommendedCoursesList');
        coursesList.innerHTML = '';

        (result.recommended_courses || []).forEach((course, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
            <td>${index + 1}</td>
            <td>${course.code}</td>
            <td>${course.name}</td>
            <td>${course.credits}</td>
            <td>${course.is_retake ? '<span class="status-badge status-retake">Học lại</span>' : `<span class="status-badge status-normal">Kỳ ${course.recommended_semester || result.next_semester || '-'}</span>`}</td>
            <td>${course.reasons?.join(', ') || '-'}</td>
        `;
            coursesList.appendChild(row);
        });

        // Hiển thị khu vực kết quả
        document.getElementById('resultsSection').style.display = 'block';
        renderAlgorithmExplanation(result);

        // Lưu lại state khi có kết quả gợi ý
        saveState();
    }

    function renderAlgorithmExplanation(result) {
        const section = document.getElementById('algorithmDetailsSection');
        if (!section) {
            return;
        }

        const dashboard = document.getElementById('reasonsDashboardContent');
        if (dashboard && result && Array.isArray(result.recommended_courses)) {
            if (result.recommended_courses.length === 0) {
                dashboard.innerHTML = '<div class="no-courses-warning">Không có môn học đề xuất nào.</div>';
            } else {
                dashboard.innerHTML = result.recommended_courses.map(course => {
                    const recSem = course.recommended_semester;
                    const nextSem = result.next_semester;
                    
                    let statusBadge = '';
                    let extraReasons = [];
                    
                    const isRequired = course.reasons && course.reasons.some(r => r.toLowerCase().includes('bắt buộc'));
                    const isSpecElective = course.reasons && course.reasons.some(r => r.toLowerCase().includes('phù hợp chuyên ngành'));

                    if (course.is_retake) {
                        statusBadge = '<span class="badge badge-danger">Học lại</span>';
                        extraReasons.push('học lại (môn chưa đạt)');
                    } else if (isSpecElective && !isRequired) {
                        statusBadge = '<span class="badge badge-primary">Tự chọn chuyên ngành</span>';
                    } else if (recSem && recSem < 99) {
                        if (recSem > nextSem) {
                            statusBadge = `<span class="badge badge-info">Học vượt (Khuyến nghị: Kỳ ${recSem})</span>`;
                            extraReasons.push(`học vượt lộ trình (khuyến nghị Kỳ ${recSem})`);
                        } else if (recSem < nextSem) {
                            statusBadge = `<span class="badge badge-warning">Học trễ (Khuyến nghị: Kỳ ${recSem})</span>`;
                            extraReasons.push(`chưa học đúng học kỳ khuyến nghị (khuyến nghị Kỳ ${recSem})`);
                        } else {
                            statusBadge = `<span class="badge badge-success">Đúng tiến độ (Kỳ ${recSem})</span>`;
                            extraReasons.push('đúng học kỳ khuyến nghị');
                        }
                    } else {
                        statusBadge = '<span class="badge badge-secondary">Tự do / Môn chung</span>';
                    }

                    // Hợp nhất lý do nguyên bản từ backend và lý do chi tiết học vượt/học lại/học trễ
                    const allReasons = [];
                    if (Array.isArray(course.reasons)) {
                        course.reasons.forEach(r => {
                            const normR = r.toLowerCase().trim();
                            if (normR && !normR.includes('học kỳ khuyến nghị') && !normR.includes('học lại')) {
                                allReasons.push(r);
                            }
                        });
                    }
                    extraReasons.forEach(r => {
                        allReasons.push(r);
                    });

                    const reasonsList = allReasons.map(r => `<span class="reason-badge">${escapeHtml(r)}</span>`).join('');
                    
                    return `
                        <div class="reasons-card">
                            <div class="reasons-card-header">
                                <span class="course-code-tag">${escapeHtml(course.code)}</span>
                                <span class="course-name-text" title="${escapeHtml(course.name)}">${escapeHtml(course.name)}</span>
                                <span class="course-credits-tag">${course.credits} TC</span>
                            </div>
                            <div class="reasons-card-body">
                                <div class="reasons-meta">
                                    ${statusBadge}
                                    <span class="priority-score-tag">Điểm ưu tiên: <strong>${Math.round(course.total_priority_score || course.heuristic_score)}</strong></span>
                                </div>
                                <div class="reasons-list-container">
                                    <strong>Lý do chọn:</strong>
                                    <div class="reasons-badges">${reasonsList}</div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }

        section.style.display = 'block';
    }

    function displayResultWarnings(result) {
        const section = document.getElementById('resultWarningsSection');
        const list = document.getElementById('resultWarningsList');
        if (!section || !list) {
            return;
        }

        const warnings = [];
        if (result?.specialization_warning) {
            warnings.push(result.specialization_warning);
        }
        if (Array.isArray(result?.warnings)) {
            result.warnings.forEach(item => {
                if (item && !warnings.includes(item)) {
                    warnings.push(item);
                }
            });
        }

        if (!warnings.length) {
            section.style.display = 'none';
            list.innerHTML = '';
            return;
        }

        list.innerHTML = warnings.map(item => `<div class="warning-item">${escapeHtml(item)}</div>`).join('');
        section.style.display = 'block';
    }

    function displayResultInsights(result) {
        const beamEl = document.getElementById('beamSearchSummary');
        const quotaEl = document.getElementById('quotaOverviewSummary');

        if (beamEl) {
            beamEl.innerHTML = result?.beam_search_details
                ? `<code>${escapeHtml(result.beam_search_details)}</code>`
                : '<span>-</span>';
        }

        if (quotaEl) {
            const quotas = result?.elective_target_quotas || {};
            const completed = result?.elective_completed_counts || {};
            const remaining = result?.elective_quota_remaining || {};
            const finalized = result?.finalized_elective_counts || {};

            const rows = ['general', 'physical', 'foundation', 'specialization'].map(key => {
                const label = {
                    general: 'Đại cương',
                    physical: 'Thể chất',
                    foundation: 'Cơ sở ngành',
                    specialization: 'Chuyên ngành',
                }[key] || key;

                return `
                    <tr>
                        <td>${label}</td>
                        <td>${completed[key] ?? 0}</td>
                        <td>${quotas[key] ?? 0}</td>
                        <td>${remaining[key] ?? 0}</td>
                        <td>${finalized[key] ?? 0}</td>
                    </tr>
                `;
            }).join('');

            quotaEl.innerHTML = `
                <table class="quota-table">
                    <thead>
                        <tr>
                            <th>Danh mục</th>
                            <th>Đã hoàn</th>
                            <th>Mục tiêu</th>
                            <th>Còn thiếu</th>
                            <th>Đã chọn</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        }
    }

    function displayEligibleCourses(courses) {
        const section = document.getElementById('eligibleCoursesSection');
        const countEl = document.getElementById('eligibleCoursesCount');
        const tbody = document.getElementById('eligibleCoursesList');
        const empty = document.getElementById('eligibleEmptyState');
        if (!section || !countEl || !tbody || !empty) {
            return;
        }

        const list = Array.isArray(courses) ? courses : [];
        countEl.textContent = String(list.length);
        tbody.innerHTML = '';

        if (!list.length) {
            empty.style.display = 'block';
            section.style.display = 'block';
            return;
        }

        empty.style.display = 'none';
        list.forEach((course, index) => {
            const row = document.createElement('tr');
            const statusLabel = course.is_retake
                ? 'Học lại'
                : `Kỳ ${course.recommended_semester || '-'}`;
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${course.code || '-'}</td>
                <td>${course.name || '-'}</td>
                <td>${course.credits ?? 0}</td>
                <td>${course.is_retake ? '<span class="status-badge status-retake">Học lại</span>' : `<span class="status-badge status-normal">${statusLabel}</span>`}</td>
                <td>${course.reasons?.join(', ') || '-'}</td>
            `;
            tbody.appendChild(row);
        });

        section.style.display = 'block';
    }

    function displayExcludedCourses(courses) {
        const section = document.getElementById('excludedCoursesSection');
        const countEl = document.getElementById('excludedCoursesCount');
        const tbody = document.getElementById('excludedCoursesList');
        const empty = document.getElementById('excludedEmptyState');
        const detail = document.getElementById('excludedCoursesDetail');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        const detailHint = document.getElementById('excludedDetailHint');
        if (!section || !countEl || !tbody || !empty || !detail || !toggleBtn || !summaryGrid || !detailHint) {
            return;
        }

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
            section.style.display = 'block';
            return;
        }

        const ruleMeta = {
            prerequisite: { label: 'Thiếu tiên quyết', className: 'attention' },
            open_semester: { label: 'Sai kỳ mở môn', className: 'attention' },
            recommended_semester: { label: 'Chưa đến kỳ khuyến nghị', className: 'normal' },
            specialization: { label: 'Chuyên ngành chưa xét/không khớp', className: 'muted' },
            major: { label: 'Không thuộc ngành học', className: 'attention' },
            already_passed: { label: 'Đã hoàn thành', className: 'muted' },
            noise_course: { label: 'Ngoài phạm vi gợi ý', className: 'muted' },
            national_defense: { label: 'Giáo dục quốc phòng', className: 'normal' },
            elective_quota: { label: 'Nhóm học phần tự chọn đã hoàn thành', className: 'normal' },
            max_credits: { label: 'Vượt giới hạn tín chỉ', className: 'attention' },
            corequisite: { label: 'Thiếu môn song hành', className: 'attention' },
            forced_semester: { label: 'Sai ràng buộc học kỳ', className: 'attention' },
            course_credit_limit: { label: 'Tín chỉ học phần quá lớn', className: 'attention' },
        };
        const countsByRule = {};
        list.forEach(course => {
            const rule = (course.failed_rules || [])[0] || 'other';
            countsByRule[rule] = (countsByRule[rule] || 0) + 1;
        });

        summaryGrid.innerHTML = Object.entries(countsByRule).map(([rule, count]) => {
            const meta = ruleMeta[rule] || { label: rule, className: 'normal' };
            return `
                <button type="button" class="excluded-summary-chip ${meta.className}" data-rule="${escapeHtml(rule)}">
                    <span>${escapeHtml(meta.label)}</span>
                    <strong>${count}</strong>
                </button>
            `;
        }).join('');

        summaryGrid.querySelectorAll('.excluded-summary-chip').forEach(chip => {
            chip.addEventListener('click', () => showExcludedCoursesByRule(chip.dataset.rule));
        });

        empty.style.display = 'none';
        toggleBtn.style.display = 'none';

        section.style.display = 'block';
    }

    function showExcludedCoursesByRule(rule) {
        const section = document.getElementById('excludedCoursesSection');
        const tbody = document.getElementById('excludedCoursesList');
        const detail = document.getElementById('excludedCoursesDetail');
        const detailHint = document.getElementById('excludedDetailHint');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!section || !tbody || !detail || !detailHint || !toggleBtn || !summaryGrid) {
            return;
        }

        let list = [];
        try {
            list = JSON.parse(section.dataset.excludedCourses || '[]');
        } catch (error) {
            list = [];
        }

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

        const detailList = list.filter(course => ((course.failed_rules || [])[0] || 'other') === rule);
        tbody.innerHTML = '';
        detailList.forEach((course, index) => {
            const currentRule = (course.failed_rules || [])[0] || '-';
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${escapeHtml(course.code || '-')}</td>
                <td>${escapeHtml(course.name || '-')}</td>
                <td>${escapeHtml((course.reasons || []).join(', ') || '-')}</td>
            `;
            tbody.appendChild(row);
        });

        summaryGrid.querySelectorAll('.excluded-summary-chip').forEach(chip => {
            chip.classList.toggle('active', chip.dataset.rule === rule);
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
        const section = document.getElementById('excludedCoursesSection');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!detail || !toggleBtn || !detailHint || !section || !summaryGrid) {
            return;
        }

        detail.style.display = 'none';
        detailHint.style.display = 'none';
        toggleBtn.style.display = 'none';
        section.dataset.selectedRule = '';
        summaryGrid.querySelectorAll('.excluded-summary-chip').forEach(chip => {
            chip.classList.remove('active');
        });
    }





    // Đặt lại form (xóa luôn state đã lưu)
    function resetForm() {
        currentStudent = null;
        currentRecommendation = null;
        sessionStorage.removeItem(SESSION_KEY);
        document.getElementById('studentSearch').value = '';
        document.getElementById('classFilterSelect').value = '';
        filterStudentsByClass();
        document.getElementById('studentSelect').value = '';
        document.getElementById('studentProfileSection').style.display = 'none';
        document.getElementById('recommendationActionSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'none';
    }

    // Hiển thị thông báo lỗi
    function showError(message, type = 'error') {
        showToast(message, type);
    }

    // Ẩn thông báo lỗi
    function hideError() {
        return;
    }
