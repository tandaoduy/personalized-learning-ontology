(function() {
    document.body.dataset.activeRole = "advisor-student-editor";

    const page = document.getElementById("advisorStudentEditorPage");
    const form = document.getElementById("learningProfileForm");
    const courseAttemptsContainer = document.getElementById("courseAttemptsContainer") || document.getElementById("courseAttemptsBody");
    const addCourseAttemptBtn = document.getElementById("addCourseAttemptBtn");
    const dialog = document.getElementById("courseAttemptDialog");
    const modalForm = document.getElementById("courseAttemptForm");
    const modalCourseSearch = document.getElementById("modalCourseSearch");
    const modalCourseCode = document.getElementById("modalCourseCode");
    const modalGrade = document.getElementById("modalGrade");
    const modalSemesterTaken = document.getElementById("modalSemesterTaken");
    const modalActualTerm = document.getElementById("modalActualTerm");
    const modalAcademicYear = document.getElementById("modalAcademicYear");
    const courseAttemptPreview = document.getElementById("courseAttemptPreview");

    const urlParams = new URLSearchParams(window.location.search);
    const targetId = (urlParams.get("id") || "").trim();
    let isEditMode = Boolean(targetId);

    const courseMap = new Map();
    let courseCatalog = [];
    let cohorts = [];
    let attempts = [];
    let allAcademicClasses = [];
    let specializationWarningShown = false;
    const attemptsDraftKey = `advisor-student-attempts:${targetId || "new"}`;

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
        await Promise.all([loadCohorts(), loadStudentProfile(), loadAllAcademicClasses()]);
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

    async function loadAllAcademicClasses() {
        try {
            const res = await fetch("/api/students/academic-classes");
            const json = await res.json();
            if (json.success && Array.isArray(json.data)) {
                allAcademicClasses = json.data;
                updateAcademicClassOptions(document.getElementById("academicClass")?.value || "");
            }
        } catch (err) {
            console.error("Lỗi nạp toàn bộ lớp:", err);
        }
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
        const selectedYear = Number(yearSelect.value);
        // Danh sách lớp chỉ đến từ API dữ liệu sinh viên.
        const cohort = cohorts.find((item) => Number(item.year_admitted) === selectedYear);
        const classes = Array.from(new Set(cohort?.academic_classes || [])).sort();

        classSelect.innerHTML = [
            `<option value="">${selectedYear ? 'Chọn lớp hành chính' : 'Chọn khóa hoặc lớp'}</option>`,
            ...classes.map((classCode) => `<option value="${escapeHtml(classCode)}">${escapeHtml(classCode)}</option>`)
        ].join("");

        const targetValue = selectedValue;
        if (targetValue && classes.includes(targetValue)) {
            classSelect.value = targetValue;
        }
    }

    async function loadCourseCatalog() {
        try {
            const response = await fetch("/api/students/courses");
            const result = await response.json();
            if (!result.success) throw new Error(result.error || "Không thể tải danh mục học phần.");

            courseCatalog = Array.isArray(result.data) ? result.data : [];
            courseMap.clear();
            courseCatalog.forEach((course) => {
                if (course?.code) {
                    courseMap.set(String(course.code).trim().toUpperCase(), course);
                }
            });
            renderCourseOptions();
        } catch (error) {
            courseCatalog = [];
            courseMap.clear();
            showAlert(error.message, "error");
        }
    }

    async function loadStudentProfile() {
        const titleEl = document.getElementById("editorPageTitle");
        const subEl = document.getElementById("editorPageSub");
        const idInput = document.getElementById("studentId");
        const bcEl = document.getElementById("breadcrumbCurrentText");

        if (!isEditMode) {
            if (titleEl) titleEl.textContent = "Thêm hồ sơ sinh viên mới";
            if (bcEl) bcEl.textContent = "Thêm hồ sơ sinh viên mới";
            if (subEl) subEl.textContent = "Tạo mới thông tin chung và nhập danh sách môn học cho sinh viên.";
            if (idInput) {
                idInput.value = "";
                idInput.readOnly = false;
                idInput.style.backgroundColor = "#ffffff";
            }
            setValue("studentName", "");
            setValue("currentSemester", 1);
            setValue("studyGoal", "đúng hạn");
            updateSpecializationOptions(NO_SPECIALIZATION);
            updateAcademicClassOptions();
            applySpecializationRule();
            attempts = [];
            renderAttempts();
            return;
        }

        if (titleEl) titleEl.textContent = "Cập nhật hồ sơ sinh viên";
        if (bcEl) bcEl.textContent = "Cập nhật hồ sơ sinh viên";
        if (subEl) subEl.textContent = "Quản lý thông tin và lịch sử học tập của sinh viên.";
        if (idInput) {
            idInput.value = targetId;
            idInput.readOnly = true;
            idInput.style.backgroundColor = "#f8fafc";
        }

        try {
            const response = await fetch(`/api/students/${encodeURIComponent(targetId)}`);
            const result = await response.json();
            if (!result.success || !result.data) {
                throw new Error(result.error || `Không tìm thấy hồ sơ sinh viên ${targetId}.`);
            }
            fillProfile(result.data);
        } catch (error) {
            showAlert(error.message, "error");
        }
    }

    function fillProfile(student) {
        setValue("studentId", student.student_id);
        setValue("studentName", student.name);
        setValue("yearAdmitted", student.year_admitted);
        setValue("major", student.major || "Công Nghệ Thông Tin");
        setValue("currentSemester", student.current_semester || 1);
        updateSpecializationOptions(student.specialization || NO_SPECIALIZATION);
        setValue("studyGoal", (student.study_goal || "đúng hạn").toLowerCase());
        updateAcademicClassOptions(student.academic_class || "");
        applySpecializationRule();

        attempts = (Array.isArray(student.course_attempts) ? student.course_attempts : []).map((attempt) => normalizeAttempt({
            code: attempt.course_code || attempt.code,
            name: attempt.course_name || attempt.name,
            semester_taken: attempt.semester_taken,
            actual_term: attempt.actual_term,
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

    function updateSpecializationOptions(selectedValue = "") {
        const major = document.getElementById("major")?.value || "Công Nghệ Thông Tin";
        const specializationSelect = document.getElementById("specialization");
        if (!specializationSelect) return;

        const options = [NO_SPECIALIZATION, ...(specializationByMajor[major] || [])];
        specializationSelect.innerHTML = options
            .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
            .join("");
        specializationSelect.value = selectedValue && options.includes(selectedValue) ? selectedValue : NO_SPECIALIZATION;
        applySpecializationRule();
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
        const container = document.getElementById("courseAttemptsBody");
        if (!container) return;
        container.innerHTML = "";
        
        if (!attempts.length) {
            container.innerHTML = `<tr><td class="learning-empty" colspan="8">Chưa có lịch sử học phần. Bấm "Thêm học phần" để nhập từng lần học.</td></tr>`;
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
                container.appendChild(row);
            });

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

    async function submitProfile(event) {
        event.preventDefault();
        clearAllErrors();

        const payload = buildPayload();
        if (!validatePayload(payload)) return;

        const submitBtn = form?.querySelector('button[type="submit"]');
        const oldText = submitBtn ? submitBtn.textContent : "💾 Lưu hồ sơ";
        if (submitBtn) {
            submitBtn.textContent = "⏳ Đang lưu...";
            submitBtn.disabled = true;
        }

        try {
            const url = isEditMode ? `/api/students/${encodeURIComponent(targetId)}` : "/api/students";
            const response = await fetch(url, {
                method: isEditMode ? "PUT" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!result.success) throw new Error(result.error || "Không thể lưu hồ sơ học tập.");

            sessionStorage.removeItem(attemptsDraftKey);
            document.dispatchEvent(new CustomEvent("form-drafts:clear", { detail: { form } }));
            showAlert(`✅ Đã ${isEditMode ? 'cập nhật' : 'thêm mới'} hồ sơ sinh viên ${payload.student_id} thành công!`, "success");
            setTimeout(() => {
                if (isEditMode) {
                    window.location.href = `/advisor/profile?student_id=${encodeURIComponent(payload.student_id)}`;
                } else {
                    window.location.href = `/advisor/students`;
                }
            }, 1200);
        } catch (error) {
            showAlert(error.message, "error");
        } finally {
            if (submitBtn) {
                submitBtn.textContent = oldText;
                submitBtn.disabled = false;
            }
        }
    }

    function buildPayload() {
        return {
            student_id: document.getElementById("studentId").value.trim(),
            name: document.getElementById("studentName").value.trim(),
            year_admitted: Number(document.getElementById("yearAdmitted").value || 2023),
            major: document.getElementById("major").value || "Công Nghệ Thông Tin",
            specialization: document.getElementById("specialization").value || NO_SPECIALIZATION,
            study_goal: document.getElementById("studyGoal").value || "đúng hạn",
            current_semester: Number(document.getElementById("currentSemester").value || 1),
            academic_class: document.getElementById("academicClass").value.trim() || "Chưa xếp lớp",
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
            ["studentId", Boolean(payload.student_id), "Vui lòng nhập mã sinh viên."],
            ["studentName", Boolean(payload.name), "Vui lòng nhập họ và tên."],
            ["academicClass", Boolean(payload.academic_class), "Vui lòng chọn lớp hành chính."],
            ["yearAdmitted", payload.year_admitted >= 2000 && payload.year_admitted <= 2030, "Vui lòng chọn khóa."],
            ["currentSemester", payload.current_semester >= 1 && payload.current_semester <= 8, "Học kỳ hiện tại phải từ 1 đến 8."],
            ["specialization", payload.current_semester < 4 || payload.specialization !== NO_SPECIALIZATION, "Sinh viên từ học kỳ 4 cần chọn chuyên ngành."],
        ].forEach(([id, condition, message]) => {
            if (!condition) {
                setFieldError(document.getElementById(id), message);
                isValid = false;
            }
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
        if (window.UIComponents && typeof window.UIComponents.showAlert === 'function') {
            window.UIComponents.showAlert(message, { type, duration: 2800 });
        } else {
            alert(message);
        }
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
