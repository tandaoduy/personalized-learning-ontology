(function() {
    document.body.dataset.activeRole = "student-profile";

    const page = document.querySelector(".student-profile-page");
    const form = document.getElementById("learningProfileForm");
    const attemptsBody = document.getElementById("courseAttemptsBody");
    const courseAttemptsContainer = document.getElementById("courseAttemptsContainer");
    const addCourseAttemptBtn = document.getElementById("addCourseAttemptBtn");
    const courseCodeList = document.getElementById("courseCodeList");
    const dialog = document.getElementById("courseAttemptDialog");
    const modalForm = document.getElementById("courseAttemptForm");
    const modalCourseSearch = document.getElementById("modalCourseSearch");
    const modalCourseCode = document.getElementById("modalCourseCode");
    const modalGrade = document.getElementById("modalGrade");
    const modalSemesterTaken = document.getElementById("modalSemesterTaken");
    const modalActualTerm = document.getElementById("modalActualTerm");
    const modalAcademicYear = document.getElementById("modalAcademicYear");
    const courseAttemptPreview = document.getElementById("courseAttemptPreview");

    const studentId = page?.dataset.studentId || "";
    const accountName = page?.dataset.accountName || "";
    const courseMap = new Map();
    let courseCatalog = [];
    let cohorts = [];
    let attempts = [];
    let pendingAcademicClass = "";
    let profileExists = false;
    let specializationRequestId = 0;
    let specializationWarningShown = false;
    const attemptsDraftKey = `student-profile-attempts:${studentId}`;

    const NO_SPECIALIZATION = "Chưa chọn chuyên ngành";
    const PASS_STATUS = "Đạt";
    const FAIL_STATUS = "Chưa đạt";
    const NO_GRADE_STATUSES = new Set(["Miễn", "Không tính điểm", "Đạt"]);

    const specializationByMajor = {
        "Công Nghệ Thông Tin": [
            "Công nghệ phần mềm",
            "Hệ Thống Thông Tin",
            "Truyền thông và Mạng máy tính",
        ],
        "Khoa học máy tính": [
            "Trí tuệ nhân tạo",
            "Khoa học dữ liệu",
        ],
    };

    init();

    async function init() {
        bindEvents();
        updateSpecializationOptions();
        renderSemesterOptions();
        restoreCachedProfile();
        await Promise.all([loadCohorts(), loadStudentProfile()]);
        await loadCourseCatalog();
        renderAttempts();
    }

    function saveAttemptsDraft() {
        try {
            sessionStorage.setItem(attemptsDraftKey, JSON.stringify(attempts));
        } catch (_) {}
    }

    function restoreAttemptsDraft() {
        try {
            const draft = JSON.parse(sessionStorage.getItem(attemptsDraftKey) || "null");
            if (Array.isArray(draft)) attempts = draft.map(normalizeAttempt);
        } catch (_) {}
    }

    function bindEvents() {
        document.getElementById("major")?.addEventListener("change", () => {
            updateSpecializationOptions();
            applySpecializationRule();
        });
        document.getElementById("currentSemester")?.addEventListener("input", () => {
            applySpecializationRule();
        });
        document.getElementById("currentSemester")?.addEventListener("change", () => {
            applySpecializationRule();
        });
        document.getElementById("specialization")?.addEventListener("change", applySpecializationRule);
        document.getElementById("yearAdmitted")?.addEventListener("change", () => {
            updateAcademicClassOptions();
            renderSemesterOptions();
            updateAttemptPreview();
        });

        addCourseAttemptBtn?.addEventListener("click", openAttemptModal);
        document.getElementById("closeCourseAttemptModal")?.addEventListener("click", closeAttemptModal);
        document.getElementById("cancelCourseAttempt")?.addEventListener("click", closeAttemptModal);
        modalCourseSearch?.addEventListener("input", renderCourseOptions);
        modalCourseSearch?.addEventListener("keydown", (e) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                modalCourseCode?.focus();
            }
        });
        modalCourseCode?.addEventListener("change", updateAttemptPreview);
        modalGrade?.addEventListener("input", updateAttemptPreview);
        modalAcademicYear?.addEventListener("change", () => {
            syncAcademicTermFields();
            updateAttemptPreview();
        });
        modalForm?.addEventListener("submit", addAttemptFromModal);
        modalForm?.querySelectorAll('input[name="modalStatus"]').forEach((input) => {
            input.addEventListener("change", () => {
                updateModalGradeState();
                updateAttemptPreview();
            });
        });

        form?.addEventListener("submit", submitProfile);
    }

    async function loadCohorts() {
        const yearSelect = document.getElementById("yearAdmitted");
        if (!yearSelect) return;

        try {
            const cohortsDataEl = document.getElementById("initialCohortsData");
            if (cohortsDataEl) {
                window.INITIAL_COHORTS = JSON.parse(cohortsDataEl.textContent);
            }

            if (window.INITIAL_COHORTS) {
                cohorts = window.INITIAL_COHORTS;
            } else {
                const response = await fetch("/api/students/cohorts");
                const result = await response.json();
                if (!result.success) throw new Error(result.error || "Không thể tải danh sách khóa.");
                cohorts = Array.isArray(result.data) ? result.data : [];
            }
            
            // If yearSelect still has 'Đang tải khóa...' or no valid options (fallback)
            if (yearSelect.options.length <= 1) {
                yearSelect.innerHTML = [
                    `<option value="">Chọn khóa</option>`,
                    ...cohorts
                        .filter((cohort) => cohort.year_admitted)
                        .map((cohort) => {
                            const label = `${cohort.label || cohort.code} - ${cohort.year_admitted}`;
                            return `<option value="${escapeHtml(cohort.year_admitted)}">${escapeHtml(label)}</option>`;
                        }),
                ].join("");
            }
            updateAcademicClassOptions();
        } catch (error) {
            cohorts = [];
            yearSelect.innerHTML = `<option value="">Chọn khóa</option>`;
            updateAcademicClassOptions();
            showAlert(error.message, "error");
        }
    }

    function updateAcademicClassOptions(selectedValue = "") {
        const classSelect = document.getElementById("academicClass");
        const yearSelect = document.getElementById("yearAdmitted");
        if (!classSelect || !yearSelect) return;
        if (selectedValue) pendingAcademicClass = selectedValue;

        const selectedYear = Number(yearSelect.value);
        if (!selectedYear) {
            classSelect.innerHTML = `<option value="">Chọn khóa trước</option>`;
            return;
        }

        const cohort = cohorts.find((item) => Number(item.year_admitted) === selectedYear);
        const classes = Array.isArray(cohort?.academic_classes) ? cohort.academic_classes : [];
        if (!classes.length) {
            classSelect.innerHTML = `<option value="">Chưa có lớp trong ontology</option>`;
            return;
        }

        classSelect.innerHTML = [
            `<option value="">Chọn lớp hành chính</option>`,
            ...classes.map((classCode) => `<option value="${escapeHtml(classCode)}">${escapeHtml(classCode)}</option>`),
        ].join("");

        const targetValue = selectedValue || pendingAcademicClass;
        if (targetValue && classes.includes(targetValue)) classSelect.value = targetValue;
    }

    async function loadCourseCatalog() {
        try {
            const response = await fetch("/api/students/courses");
            const result = await response.json();
            if (!result.success) throw new Error(result.error || "Không thể tải danh mục môn học.");

            courseCatalog = result.data || [];
            courseMap.clear();
            courseCodeList.innerHTML = "";
            courseCatalog.forEach((course) => {
                const code = String(course.code || "").trim().toUpperCase();
                if (!code) return;
                courseMap.set(code, course);
                const option = document.createElement("option");
                option.value = code;
                option.label = course.name || code;
                courseCodeList.appendChild(option);
            });
            renderCourseOptions();
            renderAttempts();
        } catch (error) {
            showAlert(error.message, "error");
        }
    }

    async function loadStudentProfile() {
        if (!studentId) return;
        try {
            const response = await fetch(`/api/students/${encodeURIComponent(studentId)}`);
            if (response.status === 404) {
                profileExists = false;
                fillNewStudentDefaults();
                return;
            }

            const result = await response.json();
            if (!result.success) throw new Error(result.error || "Không thể tải hồ sơ học tập.");

            profileExists = true;
            fillProfile(result.data);
            cacheProfile(result.data);
        } catch (error) {
            showAlert(error.message, "error");
        }
    }

    function getProfileCacheKey() {
        return `learningProfile:${studentId}`;
    }

    function restoreCachedProfile() {
        if (!studentId) return;
        try {
            const cached = sessionStorage.getItem(getProfileCacheKey());
            if (!cached) return;
            const student = JSON.parse(cached);
            if (student?.student_id) {
                profileExists = true;
                fillProfile(student);
            }
        } catch (error) {
            sessionStorage.removeItem(getProfileCacheKey());
        }
    }

    function cacheProfile(student) {
        if (!studentId || !student) return;
        try {
            sessionStorage.setItem(getProfileCacheKey(), JSON.stringify(student));
        } catch (error) {
            // Cache is only for faster paint; ignore storage limits.
        }
    }

    function fillNewStudentDefaults() {
        setValue("studentId", studentId);
        setValue("studentName", accountName);
        setValue("yearAdmitted", "");
        attempts = [];
        updateSpecializationOptions(NO_SPECIALIZATION);
        applySpecializationRule();
        renderAttempts();
    }

    function fillProfile(student) {
        setValue("studentId", student.student_id);
        setValue("studentName", student.name);
        setValue("yearAdmitted", student.year_admitted);
        setValue("major", student.major);
        updateSpecializationOptions(student.specialization);
        setValue("currentSemester", student.current_semester);
        setValue("studyGoal", student.study_goal);
        updateAcademicClassOptions(student.academic_class);
        applySpecializationRule();

        attempts = (Array.isArray(student.course_attempts) ? student.course_attempts : []).map((attempt) => normalizeAttempt({
            code: attempt.course_code,
            name: attempt.course_name,
            semester_taken: attempt.semester_taken,
            actual_term: attempt.actual_term,
            academic_year: attempt.academic_year,
            attempt_number: attempt.attempt_number,
            grade: attempt.grade,
            status: attempt.status,
            grade_specified: attempt.grade_specified,
        }));
        renderAttempts();
    }

    function setValue(id, value) {
        const element = document.getElementById(id);
        if (element && value !== undefined && value !== null) element.value = value;
    }

    function normalizeSpecializationText(value) {
        return String(value || "").normalize("NFC").trim().toLocaleLowerCase("vi-VN");
    }

    function renderSpecializationOptions(values, selectedValue = "") {
        const specializationSelect = document.getElementById("specialization");
        if (!specializationSelect) return;

        const options = [NO_SPECIALIZATION, ...Array.from(new Set(values || []))];
        specializationSelect.innerHTML = options
            .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
            .join("");

        const selected = options.find((value) =>
            normalizeSpecializationText(value) === normalizeSpecializationText(selectedValue)
        );
        specializationSelect.value = selected || NO_SPECIALIZATION;
        applySpecializationRule();
    }

    function updateSpecializationOptions(selectedValue = "") {
        const major = document.getElementById("major")?.value || "Công Nghệ Thông Tin";
        const fallback = Object.entries(specializationByMajor).find(([majorName]) =>
            normalizeSpecializationText(majorName) === normalizeSpecializationText(major)
        )?.[1] || [];
        renderSpecializationOptions(fallback, selectedValue);

        const requestId = ++specializationRequestId;
        fetch(`/api/students/specializations?major=${encodeURIComponent(major)}`)
            .then((response) => response.json())
            .then((result) => {
                const currentMajor = document.getElementById("major")?.value || "";
                if (
                    requestId !== specializationRequestId
                    || normalizeSpecializationText(currentMajor) !== normalizeSpecializationText(major)
                    || !result.success
                    || !Array.isArray(result.data)
                ) return;

                renderSpecializationOptions(result.data, selectedValue);
            })
            .catch((error) => {
                console.warn("Không thể nạp chuyên ngành từ ontology:", error);
            });
    }

    function applySpecializationRule() {
        const currentSemester = Number(document.getElementById("currentSemester")?.value || 1);
        const specializationSelect = document.getElementById("specialization");
        if (!specializationSelect) return;

        if (currentSemester < 4) {
            specializationSelect.value = NO_SPECIALIZATION;
            specializationSelect.disabled = true;
            specializationWarningShown = false;
            return;
        }

        specializationSelect.disabled = false;
        const shouldWarn = currentSemester >= 4 && specializationSelect.value === NO_SPECIALIZATION;
        if (shouldWarn && !specializationWarningShown) {
            window.UIComponents?.showAlert("Sinh viên từ học kỳ 4 cần chọn chuyên ngành.", {
                type: "warning",
                duration: 6000,
            });
        }
        specializationWarningShown = shouldWarn;
    }

    function openAttemptModal() {
        clearModalErrors();
        modalForm.reset();
        renderSemesterOptions();
        renderCourseOptions();
        updateModalGradeState();
        updateAttemptPreview();
        dialog?.showModal();
    }

    function closeAttemptModal() {
        dialog?.close();
    }

    function renderSemesterOptions() {
        if (!modalAcademicYear || !modalSemesterTaken || !modalActualTerm) return;
        const currentSemester = Number(document.getElementById("currentSemester")?.value || 1);
        const maxSemester = Math.max(1, Math.min(12, currentSemester + 2));
        const options = [];
        const admittedYear = Number(document.getElementById("yearAdmitted")?.value || 0);

        for (let actualTerm = 1; actualTerm <= maxSemester; actualTerm += 1) {
            const semesterTaken = ((actualTerm - 1) % 3) + 1;
            const offset = Math.floor((actualTerm - 1) / 3);
            const academicYear = admittedYear ? `${admittedYear + offset}-${admittedYear + offset + 1}` : "";
            let termName = semesterTaken === 3 ? "Học kỳ 3" : `Học kỳ ${semesterTaken}`;
            let label = academicYear ? `${termName} năm học ${academicYear}` : termName;
            options.push({ actualTerm, semesterTaken, academicYear, label });
        }

        modalAcademicYear.innerHTML = options.map((option) => `
            <option
                value="${escapeHtml(`${option.semesterTaken}:${option.actualTerm}`)}"
                data-semester="${escapeHtml(option.semesterTaken)}"
                data-actual-term="${escapeHtml(option.actualTerm)}"
                data-academic-year="${escapeHtml(option.academicYear)}"
            >${escapeHtml(option.label)}</option>
        `).join("");

        const defaultOption = options[options.length - 1];
        if (defaultOption) modalAcademicYear.value = `${defaultOption.semesterTaken}:${defaultOption.actualTerm}`;
        syncAcademicTermFields();
    }

    function getSemesterLabel(value) {
        const semester = Number(typeof value === "object" ? value?.semester_taken : value);
        if (semester === 1) return "Học kỳ 1";
        if (semester === 2) return "Học kỳ 2";
        if (semester === 3) return "Học kỳ 3";
        return "Chưa xác định";
    }

    function getActualTermLabel(semesterTaken, actualTerm = null) {
        return getSemesterLabel(semesterTaken);
    }

    function syncAcademicTermFields() {
        if (!modalAcademicYear || !modalSemesterTaken || !modalActualTerm) return;
        const selected = modalAcademicYear.selectedOptions?.[0];
        modalSemesterTaken.value = selected?.dataset.semester || "";
        modalActualTerm.value = selected?.dataset.actualTerm || "";
    }

    function renderCourseOptions() {
        if (!modalCourseCode) return;
        const query = (modalCourseSearch?.value || "").trim().toLowerCase();
        
        const filtered = courseCatalog.filter((course) => {
            const code = String(course.code || "").toLowerCase();
            const name = String(course.name || "").toLowerCase();
            return !query || code.includes(query) || name.includes(query);
        });

        const optionsHtml = filtered.map((course) => {
            const code = String(course.code || "").toUpperCase();
            return `<option value="${escapeHtml(code)}">${escapeHtml(code)} - ${escapeHtml(course.name || code)}</option>`;
        });

        if (optionsHtml.length === 0) {
            optionsHtml.push(`<option value="">Không tìm thấy môn học phù hợp</option>`);
        }

        modalCourseCode.innerHTML = optionsHtml.join("");
        
        updateAttemptPreview();
    }

    function updateModalGradeState() {
        const status = getSelectedModalStatus();
        const noGrade = NO_GRADE_STATUSES.has(status);
        modalGrade.disabled = noGrade;
        if (noGrade) modalGrade.value = "";
    }

    function updateAttemptPreview() {
        if (!courseAttemptPreview) return;
        const code = modalCourseCode?.value || "";
        const course = courseMap.get(code);
        const credits = course?.credits ?? course?.credit ?? "";
        const termLabel = modalAcademicYear?.selectedOptions?.[0]?.textContent || "";
        courseAttemptPreview.textContent = course
            ? `${code} - ${course.name || code}${credits !== "" ? ` | ${credits} tín chỉ` : ""} | ${termLabel || "Chưa chọn học kỳ thực tế"}`
            : "Chưa chọn môn học";
    }

    function getSelectedModalStatus() {
        return modalForm.querySelector('input[name="modalStatus"]:checked')?.value || "auto";
    }

    function addAttemptFromModal(event) {
        event.preventDefault();
        clearModalErrors();

        const code = modalCourseCode.value.trim().toUpperCase();
        const course = courseMap.get(code);
        const statusChoice = getSelectedModalStatus();
        const grade = Number(modalGrade.value || 0);
        const semesterTaken = Number(modalSemesterTaken.value || 0);
        const actualTerm = Number(modalActualTerm?.value || 0);
        const academicYear = modalAcademicYear.selectedOptions?.[0]?.dataset?.academicYear || "";

        if (!course) {
            setFieldError(modalCourseCode, "Vui lòng chọn môn học.");
            return;
        }
        if (!semesterTaken) {
            setFieldError(modalAcademicYear, "Vui lòng chọn học kỳ theo năm học.");
            return;
        }
        if (!NO_GRADE_STATUSES.has(statusChoice) && (modalGrade.value === "" || grade < 0 || grade > 10)) {
            setFieldError(modalGrade, "Điểm phải từ 0 đến 10.");
            return;
        }

        let finalStatus = "";
        let finalGrade = 0.0;
        let gradeSpecified = false;

        if (statusChoice === "Miễn" || statusChoice === "Không tính điểm" || statusChoice === "Đạt") {
            finalStatus = statusChoice;
            finalGrade = statusChoice === "Đạt" ? 5.0 : 0.0;
            gradeSpecified = false;
        } else {
            finalStatus = grade >= 5.0 ? PASS_STATUS : FAIL_STATUS;
            finalGrade = grade;
            gradeSpecified = true;
        }

        const attemptNumber = attempts.filter((item) => item.code === code).length + 1;

        attempts.push(normalizeAttempt({
            code,
            name: course.name || code,
            semester_taken: semesterTaken,
            actual_term: actualTerm,
            academic_year: academicYear,
            attempt_number: attemptNumber,
            grade: finalGrade,
            status: finalStatus,
            grade_specified: gradeSpecified,
        }));
        renumberAttempts(code);
        renderAttempts();
        
        if (modalCourseSearch) modalCourseSearch.value = "";
        renderCourseOptions();
        if (modalGrade) {
            modalGrade.value = "";
            modalGrade.disabled = false;
        }
        const statusRadios = modalForm.querySelectorAll('input[name="modalStatus"]');
        if (statusRadios.length > 0) statusRadios[0].checked = true;
        updateAttemptPreview();
        
        showAlert(`Đã thêm môn ${course.name || code} thành công!`, "success");
        if (modalCourseSearch) modalCourseSearch.focus();
    }

    function normalizeAttempt(attempt) {
        const code = String(attempt.code || "").trim().toUpperCase();
        const semesterTaken = Number(attempt.semester_taken || 0);
        const actualTerm = Number(attempt.actual_term || 0);
        const status = String(attempt.status || FAIL_STATUS);
        return {
            code,
            name: attempt.name || courseMap.get(code)?.name || code,
            semester_taken: semesterTaken,
            actual_term: actualTerm,
            academic_year: attempt.academic_year || "",
            attempt_number: Number(attempt.attempt_number || 1),
            grade: Number(attempt.grade || 0),
            status,
            grade_specified: attempt.grade_specified ?? !NO_GRADE_STATUSES.has(status),
        };
    }

    function renumberAttempts(code) {
        attempts
            .filter((item) => item.code === code)
            .sort((a, b) => {
                const termDiff = Number(a.actual_term || 0) - Number(b.actual_term || 0);
                if (termDiff !== 0) return termDiff;
                return (Number(a.attempt_number || 1) - Number(b.attempt_number || 1));
            })
            .forEach((item, index) => {
                item.attempt_number = index + 1;
            });
    }

    function renderAttempts() {
        if (courseAttemptsContainer) courseAttemptsContainer.innerHTML = "";
        const container = document.getElementById("courseAttemptsBody") || courseAttemptsContainer;
        if (container) container.innerHTML = "";
        
        if (!attempts.length) {
            if (container) container.innerHTML = `<tr><td class="learning-empty" colspan="8">Chưa có lịch sử học phần. Bấm "Thêm học phần" để nhập từng lần học.</td></tr>`;
            return;
        }

        attempts
            .slice()
            .sort((a, b) => {
                const termDifference = Number(a.actual_term || 0) - Number(b.actual_term || 0);
                if (termDifference !== 0) return termDifference;
                const attemptDifference = Number(a.attempt_number || 1) - Number(b.attempt_number || 1);
                if (attemptDifference !== 0) return attemptDifference;
                return String(a.code || "").localeCompare(String(b.code || ""));
            })
            .forEach((attempt) => {
                const originalIndex = attempts.indexOf(attempt);
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td><strong>${escapeHtml(attempt.code)}</strong></td>
                    <td>${escapeHtml(attempt.name)}</td>
                    <td>${escapeHtml(getSemesterLabel(attempt.semester_taken))}</td>
                    <td>${escapeHtml(attempt.academic_year || "-")}</td>
                    <td>Lần ${escapeHtml(attempt.attempt_number)}</td>
                    <td>${escapeHtml(formatGradeDisplay(attempt))}</td>
                    <td><span class="attempt-status-badge ${getStatusClass(attempt.status)}">${escapeHtml(attempt.status)}</span></td>
                    <td><button class="learning-row-remove" type="button" data-index="${originalIndex}" title="Xóa học phần">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                    </button></td>
                `;
                if (container) container.appendChild(row);
            });

        if (container) {
            container.querySelectorAll(".learning-row-remove").forEach((button) => {
                button.addEventListener("click", () => {
                    const index = Number(button.dataset.index);
                    const code = attempts[index]?.code;
                    attempts.splice(index, 1);
                if (code) renumberAttempts(code);
                renderAttempts();
                });
            });
        }
    }

    async function submitProfile(event) {
        event.preventDefault();
        clearAllErrors();

        const payload = buildPayload();
        if (!validatePayload(payload)) return;

        try {
            const url = profileExists ? `/api/students/${encodeURIComponent(payload.student_id)}` : "/api/students";
            const response = await fetch(url, {
                method: profileExists ? "PUT" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!result.success) throw new Error(result.error || "Không thể lưu hồ sơ học tập.");

            profileExists = true;
            fillProfile(result.data);
            cacheProfile(result.data);
            sessionStorage.removeItem(attemptsDraftKey);
            document.dispatchEvent(new CustomEvent("form-drafts:clear", { detail: { form } }));
            showAlert("Đã lưu hồ sơ học tập vào DanhSachSinhVien.json.", "success");
        } catch (error) {
            showAlert(error.message, "error");
        }
    }

    function buildPayload() {
        return {
            student_id: document.getElementById("studentId").value.trim(),
            name: document.getElementById("studentName").value.trim(),
            year_admitted: Number(document.getElementById("yearAdmitted").value || 2023),
            major: document.getElementById("major").value,
            specialization: document.getElementById("specialization").value,
            study_goal: document.getElementById("studyGoal").value,
            current_semester: Number(document.getElementById("currentSemester").value || 1),
            academic_class: document.getElementById("academicClass").value.trim(),
            courses: attempts.map((attempt) => ({
                code: attempt.code,
                name: attempt.name,
                semester_taken: attempt.semester_taken,
                actual_term: attempt.actual_term,
                academic_year: attempt.academic_year,
                attempt_number: attempt.attempt_number,
                grade: attempt.grade,
                status: attempt.status,
                grade_specified: attempt.grade_specified,
            })),
        };
    }

    function validatePayload(payload) {
        let isValid = true;
        [
            ["studentName", payload.name, "Vui lòng nhập họ và tên."],
            ["academicClass", payload.academic_class, "Vui lòng nhập lớp hành chính."],
            ["yearAdmitted", payload.year_admitted >= 2000 && payload.year_admitted <= 2030, "Vui lòng chọn khóa."],
            ["currentSemester", payload.current_semester >= 1 && payload.current_semester <= 8, "Học kỳ hiện tại phải từ 1 đến 8."],
            ["specialization", payload.current_semester < 4 || payload.specialization !== NO_SPECIALIZATION, "Sinh viên từ học kỳ 4 cần chọn chuyên ngành."],
        ].forEach(([id, condition, message]) => {
            if (!condition) {
                setFieldError(document.getElementById(id), message);
                isValid = false;
            }
        });

        payload.courses.forEach((course) => {
            if (!courseMap.has(course.code)) isValid = false;
        });

        if (!isValid) showAlert("Vui lòng kiểm tra lại thông tin hồ sơ.", "error");
        return isValid;
    }

    function setFieldError(input, message) {
        if (!input) return;
        input.classList.add("is-invalid");
        const wrapper = input.closest(".learning-field") || input.closest("td");
        const error = wrapper?.querySelector("small");
        if (error) error.textContent = message;
    }

    function clearModalErrors() {
        modalForm?.querySelectorAll(".is-invalid").forEach((item) => item.classList.remove("is-invalid"));
        modalForm?.querySelectorAll("small").forEach((item) => {
            item.textContent = "";
        });
    }

    function clearAllErrors() {
        document.querySelectorAll(".is-invalid").forEach((item) => item.classList.remove("is-invalid"));
        document.querySelectorAll(".learning-field small").forEach((item) => {
            item.textContent = "";
        });
    }

    function getStatusClass(status) {
        if (status === PASS_STATUS || NO_GRADE_STATUSES.has(status)) return "attempt-status-badge--pass";
        return "attempt-status-badge--fail";
    }

    function formatGrade(value) {
        return Number(value || 0).toFixed(1);
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

    function showAlert(message, type = "info") {
        window.UIComponents?.showAlert(message, { type, duration: 2800 });
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }
})();
