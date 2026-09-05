(function() {
    document.body.dataset.activeRole = "student-history";

    const container = document.getElementById("historyPageContainer");
    const summaryCardContainer = document.getElementById("studentSummaryCard");
    const courseAttemptsContainer = document.getElementById("courseAttemptsContainer");

    const studentId = container?.dataset.studentId || "";
    const accountName = container?.dataset.accountName || "";

    function readInitialJson(id, fallback = null) {
        const element = document.getElementById(id);
        if (!element) return fallback;
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error(`Không thể đọc dữ liệu từ #${id}:`, error);
            return fallback;
        }
    }

    const courseMap = new Map();
    let courseCatalog = readInitialJson("initialCourseData", []);
    let studentData = readInitialJson("initialStudentData", null);

    const NO_SPECIALIZATION = "Chưa chọn chuyên ngành";
    const PASS_STATUS = "Đạt";
    const NO_GRADE_STATUSES = new Set(["Miễn", "Không tính điểm"]);

    async function init() {
        if (!studentId) {
            showEmpty("Không tìm thấy thông tin sinh viên.");
            return;
        }

        try {
            if (Array.isArray(courseCatalog) && courseCatalog.length) {
                buildCourseMap();
            }

            if (studentData) {
                renderPage();
                return;
            }

            await Promise.all([
                loadCourseCatalog(),
                loadStudentProfile(studentId)
            ]);

            renderPage();
        } catch (error) {
            console.error("Error initializing history page:", error);
            showEmpty("Đã xảy ra lỗi khi tải dữ liệu kết quả học tập.");
        }
    }

    function buildCourseMap() {
        courseMap.clear();
        courseCatalog.forEach((course) => {
            const code = String(course.code || "").trim().toUpperCase();
            if (code) {
                courseMap.set(code, course);
            }
        });
    }

    async function loadCourseCatalog() {
        const response = await fetch("/api/students/courses");
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || "Không thể tải danh mục môn học.");
        }
        
        courseCatalog = Array.isArray(result.data) ? result.data : [];
        buildCourseMap();
    }

    async function loadStudentProfile(id) {
        const cacheKey = `studentHistory:${id}`;
        const cached = sessionStorage.getItem(cacheKey);

        if (cached) {
            try {
                studentData = JSON.parse(cached);
                renderPage();
            } catch (_) {
                sessionStorage.removeItem(cacheKey);
            }
        }

        const response = await fetch(`/api/students/${encodeURIComponent(id)}`);
        const result = await response.json();

        if (!result.success) {
            if (!studentData) {
                studentData = null;
            }
            return;
        }

        studentData = result.data;
        sessionStorage.setItem(cacheKey, JSON.stringify(studentData));
        renderPage();
    }

    function showEmpty(message) {
        if (courseAttemptsContainer) {
            courseAttemptsContainer.innerHTML = `<div class="learning-empty-state"><p>${escapeHtml(message)}</p></div>`;
        }
    }

    function formatGrade(value) {
        const num = Number(value);
        return isNaN(num) ? "0.0" : num.toFixed(1);
    }

    function formatGradeDisplay(attempt) {
        if (attempt.status === "Không tính điểm" || attempt.status === "Miễn") {
            return attempt.status;
        }
        if (attempt.status === "Đạt" && (attempt.grade === 0 || attempt.grade === 0.0 || attempt.grade === "0" || attempt.grade === "0.0" || attempt.grade_specified === false || attempt.grade === undefined || attempt.grade === null)) {
            return "Điểm đạt";
        }
        if (attempt.grade !== undefined && attempt.grade !== null && attempt.grade !== "") {
            return formatGrade(attempt.grade);
        }
        return attempt.status || "-";
    }

    function getStatusClass(status) {
        if (status === "Đạt") return "status-pass";
        if (status === "Chưa đạt") return "status-fail";
        return "status-exempt";
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    // semester_taken is the semester inside the recorded academic year.
    // actual_term is only used to order attempts across the whole study path.
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

    function calculateAcademicMetrics(attempts) {
        const courseSummaryMap = {};
        
        attempts.forEach(attempt => {
            const key = attempt.code;
            if (!key) return;
            
            if (!courseSummaryMap[key]) {
                const courseInfo = courseMap.get(attempt.code);
                courseSummaryMap[key] = {
                    code: attempt.code,
                    name: attempt.name,
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

    function renderPage() {
        if (!studentData) {
            showEmpty("Hồ sơ học tập trống. Vui lòng cập nhật hồ sơ ở mục Hồ sơ của bạn.");
            return;
        }

        const attempts = (studentData.course_attempts || []).map(a => ({
            ...a,
            code: a.course_code,
            name: a.course_name
        }));
        const metrics = calculateAcademicMetrics(attempts);

        // Render Summary Card
        const studentName = studentData.name || accountName || "";
        const initials = studentName.split(" ").pop()?.[0]?.toUpperCase() || "S";
        const major = studentData.major || "";
        const specialization = studentData.specialization || "";
        const academicClass = studentData.academic_class || "";
        const currentSemester = studentData.current_semester || "";
        const yearAdmitted = studentData.year_admitted || "";
        const targetGoal = studentData.study_goal || "";

        summaryCardContainer.style.display = "block";
        summaryCardContainer.innerHTML = `
            <div class="student-summary-card">
                <div class="student-summary-card__header">
                    <div class="student-summary-card__avatar">${escapeHtml(initials)}</div>
                    <div class="student-summary-card__title">
                        <h3>${escapeHtml(studentData.student_id || studentId)}</h3>
                        <p>${escapeHtml(studentName)}</p>
                    </div>
                    <div class="student-summary-card__actions" style="margin-left: auto;">
                        <button class="ui-btn ui-btn--primary" id="printTranscriptBtn" type="button" style="display: flex; align-items: center; gap: 8px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                            In bảng điểm
                        </button>
                    </div>
                </div>
                <div class="student-summary-card__grid">
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Ngành học</span>
                        <span class="student-summary-card__value">${escapeHtml(major)}</span>
                    </div>
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Chuyên ngành</span>
                        <span class="student-summary-card__value">${escapeHtml(specialization === NO_SPECIALIZATION ? "-" : specialization || "-")}</span>
                    </div>
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Lớp</span>
                        <span class="student-summary-card__value">${escapeHtml(academicClass)}</span>
                    </div>
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Học kỳ hiện tại</span>
                        <span class="student-summary-card__value">Kỳ ${escapeHtml(currentSemester)}</span>
                    </div>
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Năm vào học</span>
                        <span class="student-summary-card__value">${escapeHtml(yearAdmitted)}</span>
                    </div>
                    <div class="student-summary-card__item">
                        <span class="student-summary-card__label">Mục tiêu</span>
                        <span class="student-summary-goal-badge ${targetGoal === "Đúng hạn" ? "goal-pass" : "goal-exempt"}">${escapeHtml(targetGoal)}</span>
                    </div>
                    <div class="student-summary-card__item stat-box primary-stat">
                        <span class="student-summary-card__label">Tín chỉ tích lũy</span>
                        <span class="student-summary-card__value stat-value">${escapeHtml(String(metrics.totalCredits))}</span>
                    </div>
                    <div class="student-summary-card__item stat-box success-stat">
                        <span class="student-summary-card__label">Điểm TB tích lũy</span>
                        <span class="student-summary-card__value stat-value">${escapeHtml(String(metrics.gpa))}</span>
                    </div>
                </div>
            </div>
        `;

        // Render Attempts Table
        courseAttemptsContainer.innerHTML = "";
        
        if (!attempts.length) {
            showEmpty("Chưa có lịch sử học phần.");
            return;
        }

        const groups = new Map();
        attempts.forEach(attempt => {
            const actualTerm = Number(attempt.actual_term || 0);
            const semesterTaken = Number(attempt.semester_taken || 0);
            const academicYear = attempt.academic_year || "";
            const groupKey = `${actualTerm}|${semesterTaken}|${academicYear}`;
            if (!groups.has(groupKey)) {
                groups.set(groupKey, {
                    semesterTaken,
                    actualTerm,
                    academicYear,
                    items: []
                });
            }
            groups.get(groupKey).items.push(attempt);
        });

        const sortedGroups = Array.from(groups.values()).sort((a, b) => {
            return (Number(a.actualTerm) || 0) - (Number(b.actualTerm) || 0);
        });

        sortedGroups.forEach(group => {
            const groupMetrics = calculateAcademicMetrics(group.items);

            const groupDiv = document.createElement("div");
            groupDiv.className = "semester-group";
            
            const groupHeader = document.createElement("div");
            groupHeader.className = "semester-group-header";
            groupHeader.innerHTML = `
                <span>${escapeHtml(getSemesterLabel(group.semesterTaken))} năm học ${escapeHtml(group.academicYear || "Chưa cập nhật")}</span>
            `;
            groupDiv.appendChild(groupHeader);

            const tableContainer = document.createElement("div");
            tableContainer.className = "learning-attempt-table";
            
            const table = document.createElement("table");
            table.dataset.pagination = "off";
            table.innerHTML = `
                <thead>
                    <tr>
                        <th>Mã môn</th>
                        <th>Tên môn học</th>
                        <th style="text-align: center;">TC</th>
                        <th style="text-align: center;">Điểm</th>
                        <th style="text-align: center;">Trạng thái</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;
            
            const tbody = table.querySelector("tbody");
            
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
                    const credits = courseInfo ? courseInfo.credits : "-";
                    
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td><strong>${escapeHtml(attempt.code)}</strong></td>
                        <td>${escapeHtml(attempt.name)}</td>
                        <td style="text-align: center;">${escapeHtml(String(credits))}</td>
                        <td style="text-align: center;">${escapeHtml(formatGradeDisplay(attempt))}</td>
                        <td style="text-align: center;"><span class="attempt-status-badge ${getStatusClass(attempt.status)}">${escapeHtml(attempt.status)}</span></td>
                    `;
                    tbody.appendChild(row);
                });
                
            tableContainer.appendChild(table);
            groupDiv.appendChild(tableContainer);
            
            const groupFooter = document.createElement("div");
            groupFooter.className = "semester-group-footer";
            groupFooter.innerHTML = `
                <span>Tổng số tín chỉ đạt: <strong><span style="color: #0ea5e9;">${groupMetrics.totalCredits}</span></strong></span>
                <span>Điểm trung bình học kỳ: <strong style="color: ${Number(groupMetrics.gpa) >= 5 ? '#10b981' : '#ef4444'};">${groupMetrics.gpa}</strong></span>
            `;
            groupDiv.appendChild(groupFooter);
            courseAttemptsContainer.appendChild(groupDiv);
        });
        
        const printBtn = document.getElementById("printTranscriptBtn");
        if (printBtn) {
            // Remove old listeners to avoid multiple fires if renderPage is called multiple times
            const newPrintBtn = printBtn.cloneNode(true);
            printBtn.parentNode.replaceChild(newPrintBtn, printBtn);
            newPrintBtn.addEventListener("click", () => {
                preparePrintTemplate(metrics, attempts);
                window.print();
            });
        }
    }
    
    function preparePrintTemplate(metrics, attempts) {
        let printSection = document.getElementById("printSection");
        if (!printSection) {
            printSection = document.createElement("div");
            printSection.id = "printSection";
            document.body.appendChild(printSection);
        }
        
        const studentName = studentData.name || accountName || "";
        const major = studentData.major || "";
        const academicClass = studentData.academic_class || "";
        const studentIdToDisplay = studentData.student_id || studentId || "";
        
        const yearAdmitted = studentData.year_admitted || "";
        
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
        
        printSection.innerHTML = `
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
    }
    
    init();
})();
