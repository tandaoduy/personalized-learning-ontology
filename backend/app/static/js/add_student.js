const courseCatalog = [];
const specializationOptions = [];
const NON_ACCUMULATED_ENGLISH_COURSES = new Set(['FLS310', 'FLS312', 'FLS313']);
const NON_ACCUMULATED_FIXED_COURSES = new Set(['SOT301']);

function isNonAccumulatedCourse(code, name = '') {
    const normalizedCode = String(code || '').trim().toUpperCase();
    const normalizedName = String(name || '').trim().toLowerCase();
    return NON_ACCUMULATED_ENGLISH_COURSES.has(normalizedCode)
        || NON_ACCUMULATED_FIXED_COURSES.has(normalizedCode)
        || normalizedName.includes('giáo dục thể chất');
}
const majorOptions = [];
let displayedCourses = [];
let studentCourses = [];
let pendingGradeChange = null;

const createForm = document.getElementById('createStudentForm');
const courseModalBackdrop = document.getElementById('courseModalBackdrop');
const courseSelect = document.getElementById('courseSelect');
const courseSearch = document.getElementById('courseSearch');
const courseGrade = document.getElementById('courseGrade');
const selectedCourseInfo = document.getElementById('selectedCourseInfo');
const tableWrap = document.getElementById('studentCoursesTableWrap');
const tableBody = document.getElementById('studentCoursesTableBody');
const emptyState = document.getElementById('emptyCourseState');
const specializationSelect = document.getElementById('specialization');
const majorSelect = document.getElementById('major');
const academicClassSelect = document.getElementById('academicClass');
const specializationHint = document.getElementById('specializationHint');
const currentSemesterInput = document.getElementById('currentSemester');

// Wrapper cho nhóm radio "courseStatus" để dùng như select
const courseStatusSelect = {
    get value() {
        const checked = document.querySelector('input[name="courseStatus"]:checked');
        return checked ? checked.value : 'auto';
    },
    set value(v) {
        const radio = document.querySelector(`input[name="courseStatus"][value="${v}"]`);
        if (radio) radio.checked = true;
    },
    addEventListener(event, handler) {
        document.querySelectorAll('input[name="courseStatus"]').forEach(r => {
            r.addEventListener('change', handler);
        });
    }
};
const formFieldIds = [
    'studentId',
    'studentName',
    'yearAdmitted',
    'currentSemester',
    'major',
    'specialization',
    'studyGoal',
    'academicClass',
];

document.addEventListener('DOMContentLoaded', async () => {
    // Tải ngành học, danh mục môn học, và lớp hành chính
    await Promise.all([loadCourseCatalog(), loadMajors(), loadAcademicClasses()]);

    if (typeof EDIT_MODE_ID !== 'undefined' && EDIT_MODE_ID) {
        await loadEditStudentData(EDIT_MODE_ID);
        loadDraft();
    } else {
        loadDraft();
        const selectedMajor = majorSelect.value;
        await loadSpecializations(selectedMajor);
        
        const draftVal = document.getElementById('specialization').dataset.draftValue;
        if (draftVal) {
            document.getElementById('specialization').value = draftVal;
        }
    }

    bindEvents();
    renderCourseTable();
    updateSpecializationState();

    // Ràng buộc chỉ nhập số cho các ô nhập mã sinh viên, năm vào học, học kỳ hiện tại
    const numberFields = ['studentId', 'yearAdmitted', 'currentSemester'];
    numberFields.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (!/[0-9]/.test(e.key)) {
                    e.preventDefault();
                }
            });
            input.addEventListener('input', function(e) {
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }
    });

    // Giới hạn giá trị nhập của courseGrade từ 0 đến 10
    const gradeInput = document.getElementById('courseGrade');
    if (gradeInput) {
        gradeInput.addEventListener('input', function() {
            let val = this.value;
            if (val === '') return;
            let num = parseFloat(val);
            if (!isNaN(num)) {
                if (num < 0) this.value = '0';
                else if (num > 10) this.value = '10';
            }
        });
    }
});

async function loadEditStudentData(studentId) {
    try {
        const response = await fetch(`/api/students/${studentId}`);
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Không tải được dữ liệu sinh viên');
        }
        
        const data = result.data;
        document.getElementById('studentId').value = String(data.student_id).replace(/[^0-9]/g, '');
        document.getElementById('studentName').value = data.name;
        document.getElementById('yearAdmitted').value = data.year_admitted;
        document.getElementById('currentSemester').value = data.current_semester;
        
        majorSelect.value = data.major || 'Công Nghệ Thông Tin';
        await loadSpecializations(data.major || 'Công Nghệ Thông Tin');
        
        specializationSelect.value = data.specialization || '';
        document.getElementById('studyGoal').value = data.study_goal || 'đúng hạn';
        academicClassSelect.value = data.academic_class || '';
        
        // Ưu tiên dùng course_attempts để khôi phục đầy đủ cả các lần học lại
        if (Array.isArray(data.course_attempts) && data.course_attempts.length > 0) {
            studentCourses = data.course_attempts.map(attempt => {
                const courseInfo = courseCatalog.find(c => c.code === attempt.course_code);
                return {
                    code: attempt.course_code,
                    name: courseInfo ? courseInfo.name : (attempt.course_name || attempt.course_code),
                    grade: attempt.grade,
                    status: attempt.status,
                    credits: courseInfo ? courseInfo.credits : 0,
                    gradeSpecified: attempt.grade_specified !== false,
                    semesterTaken: attempt.semester_taken || 0,
                    attemptNumber: attempt.attempt_number || 1,
                };
            });
        } else {
            // Tương thích ngược với dữ liệu cũ không có course_attempts
            studentCourses = Object.keys(data.course_grades || {}).map(code => {
                const courseInfo = courseCatalog.find(c => c.code === code);
                const status = (data.course_statuses || {})[code] || 'Chưa đạt';
                const grade = data.course_grades[code];
                return {
                    code: code,
                    name: courseInfo ? courseInfo.name : code,
                    grade: grade,
                    status: status,
                    credits: courseInfo ? courseInfo.credits : 0,
                    gradeSpecified: (data.course_grade_specified && data.course_grade_specified[code] !== undefined)
                        ? data.course_grade_specified[code]
                        : !(['Miễn', 'Không tính điểm'].includes(status)),
                    semesterTaken: 0,
                    attemptNumber: 1,
                };
            });
        }
        
    } catch (error) {
        showToast('Không thể tải thông tin sinh viên để chỉnh sửa', 'error');
    }
}

async function populateNextStudentId() {
    const studentIdInput = document.getElementById('studentId');
    if (!studentIdInput) {
        return;
    }

    try {
        const response = await fetch('/api/students/next-id');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không lấy được mã sinh viên tự động');
        }

        const nextId = (result.data || {}).student_id;
        if (!nextId) {
            throw new Error('Không lấy được mã sinh viên tự động');
        }

        studentIdInput.value = String(nextId).replace(/[^0-9]/g, '');
    } catch (error) {
        // Dự phòng: tính từ danh sách sinh viên hiện có
        try {
            const resp = await fetch('/api/students');
            const data = await resp.json();
            if (!data.success) {
                throw new Error(data.error || 'Không tải được danh sách sinh viên');
            }

            const list = Array.isArray(data.data) ? data.data : [];
            let maxNum = 0;
            list.forEach(item => {
                const raw = String((item || {}).student_id || '').trim().toUpperCase();
                const match = raw.match(/(\d+)/);
                if (!match) {
                    return;
                }
                const num = Number(match[1]);
                if (Number.isFinite(num) && num > maxNum) {
                    maxNum = num;
                }
            });

            studentIdInput.value = String(maxNum + 1);
        } catch (fallbackError) {
            showToast('Không thể tự động tạo mã sinh viên. Vui lòng tải lại trang.', 'warning');
        }
    }
}

function bindEvents() {
    document.getElementById('openCourseModalBtn').addEventListener('click', openCourseModal);
    document.getElementById('closeCourseModalBtn').addEventListener('click', closeCourseModal);
    document.getElementById('cancelCourseBtn').addEventListener('click', closeCourseModal);
    document.getElementById('saveCourseBtn').addEventListener('click', saveCourseFromModal);
    document.getElementById('resetCreateFormBtn').addEventListener('click', resetCreateStudentForm);
    document.getElementById('confirmGradeChangeBtn').addEventListener('click', confirmGradeChange);
    document.getElementById('cancelGradeChangeBtn').addEventListener('click', cancelGradeChange);
    document.getElementById('closeGradeChangeModalBtn').addEventListener('click', cancelGradeChange);
    document.getElementById('addNewAttemptBtn').addEventListener('click', addNewAttempt);
    document.getElementById('gradeChangeModalBackdrop').addEventListener('click', event => {
        if (event.target === document.getElementById('gradeChangeModalBackdrop')) {
            cancelGradeChange();
        }
    });
    
    // Hỗ trợ nhấn Enter để lưu môn học nhanh trong cả modal thêm môn học
    document.querySelector('.course-modal').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation(); // Ngăn sự kiện nổi bọt lên window gây tự động xác nhận ở modal sau
            document.getElementById('saveCourseBtn').click();
        }
    });

    // Hỗ trợ nhấn Enter trong modal xác nhận thay đổi điểm
    window.addEventListener('keydown', (e) => {
        const gradeChangeModal = document.getElementById('gradeChangeModalBackdrop');
        if (gradeChangeModal && gradeChangeModal.style.display === 'block') {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('confirmGradeChangeBtn').click();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelGradeChange();
            }
        }
    });

    courseSearch.addEventListener('input', filterCourseOptions);
    
    // Hỗ trợ phím mũi tên lên/xuống để di chuyển nhanh giữa ô tìm kiếm và danh sách chọn môn học
    courseSearch.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            courseSelect.focus();
            if (courseSelect.options.length > 0 && courseSelect.selectedIndex === -1) {
                courseSelect.selectedIndex = 0;
                updateSelectedCourseInfo();
            }
        }
    });

    courseSelect.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowUp' && courseSelect.selectedIndex <= 0) {
            e.preventDefault();
            courseSearch.focus();
        }
    });

    courseSelect.addEventListener('change', updateSelectedCourseInfo);
    courseStatusSelect.addEventListener('change', () => {
        const val = courseStatusSelect.value;
        if (val === 'Không tính điểm' || val === 'Miễn' || val === 'Đạt') {
            courseGrade.disabled = true;
            courseGrade.value = '';
        } else {
            courseGrade.disabled = false;
        }
    });
    currentSemesterInput.addEventListener('input', updateSpecializationState);
    createForm.addEventListener('submit', submitCreateStudentForm);
    createForm.addEventListener('input', saveDraft);
    createForm.addEventListener('change', saveDraft);
    window.addEventListener('beforeunload', saveDraft);

    // Khi thay đổi ngành học, tải lại danh sách chuyên ngành tương ứng
    majorSelect.addEventListener('change', async () => {
        const selectedMajor = majorSelect.value;
        await loadSpecializations(selectedMajor);
        updateSpecializationState();
    });

    formFieldIds.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', () => clearFieldError(fieldId));
            field.addEventListener('change', () => clearFieldError(fieldId));
        }
    });
    courseModalBackdrop.addEventListener('click', event => {
        if (event.target === courseModalBackdrop) {
            closeCourseModal();
        }
    });
}

async function loadCourseCatalog() {
    try {
        const response = await fetch('/api/students/courses');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không tải được danh mục môn học');
        }

        courseCatalog.push(...(result.data || []));
        displayedCourses = [...courseCatalog];
        renderCourseOptions(displayedCourses);
    } catch (error) {
        showCreateError('Không thể tải danh mục môn học: ' + error.message);
    }
}

async function loadSpecializations(major = '') {
    try {
        const url = major ? `/api/students/specializations?major=${encodeURIComponent(major)}` : '/api/students/specializations';
        const response = await fetch(url);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không tải được chuyên ngành');
        }

        specializationOptions.length = 0; // Xóa danh sách cũ
        specializationOptions.push(...(result.data || []));
        renderSpecializationOptions(Boolean(major));
    } catch (error) {
        showCreateError('Không thể tải danh sách chuyên ngành: ' + error.message);
    }
}

function renderSpecializationOptions(majorSelected = false) {
    specializationSelect.innerHTML = '';

    if (!majorSelected) {
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '-- Vui lòng chọn ngành học trước --';
        specializationSelect.appendChild(defaultOption);
        return;
    }

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '-- Chọn chuyên ngành --';
    specializationSelect.appendChild(defaultOption);

    const noSpecOption = document.createElement('option');
    noSpecOption.value = 'Chưa chọn chuyên ngành';
    noSpecOption.textContent = 'Chưa chọn chuyên ngành';
    specializationSelect.appendChild(noSpecOption);

    specializationOptions.forEach(optionValue => {
        if (optionValue !== 'Chưa chọn chuyên ngành') {
            const option = document.createElement('option');
            option.value = optionValue;
            option.textContent = optionValue;
            specializationSelect.appendChild(option);
        }
    });
}

async function loadMajors() {
    try {
        const response = await fetch('/api/students/majors');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không tải được ngành học');
        }

        majorOptions.push(...(result.data || []));
        renderMajorOptions();
    } catch (error) {
        showCreateError('Không thể tải danh sách ngành học: ' + error.message);
    }
}

function renderMajorOptions() {
    majorSelect.innerHTML = '';

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '-- Chọn ngành học --';
    majorSelect.appendChild(defaultOption);

    majorOptions.forEach(optionValue => {
        const option = document.createElement('option');
        option.value = optionValue;
        option.textContent = optionValue;
        majorSelect.appendChild(option);
    });
}

const academicClassOptions = [];

async function loadAcademicClasses() {
    try {
        const response = await fetch('/api/students/academic-classes');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không tải được danh sách lớp hành chính');
        }

        academicClassOptions.push(...(result.data || []));
        renderAcademicClassOptions();
    } catch (error) {
        showCreateError('Không thể tải danh sách lớp hành chính: ' + error.message);
    }
}

function renderAcademicClassOptions() {
    academicClassSelect.innerHTML = '';

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '-- Chọn lớp hành chính --';
    academicClassSelect.appendChild(defaultOption);

    academicClassOptions.forEach(optionValue => {
        const option = document.createElement('option');
        option.value = optionValue;
        option.textContent = optionValue;
        academicClassSelect.appendChild(option);
    });
}

function updateSpecializationState() {
    const semester = Number(currentSemesterInput.value || 1);
    const locked = semester < 4;

    if (locked) {
        let option = specializationSelect.querySelector('option[value="Chưa chọn chuyên ngành"]');
        if (!option) {
            option = document.createElement('option');
            option.value = 'Chưa chọn chuyên ngành';
            option.textContent = 'Chưa chọn chuyên ngành';
            specializationSelect.appendChild(option);
        }
        
        if (specializationSelect.value && specializationSelect.value !== 'Chưa chọn chuyên ngành') {
            specializationSelect.dataset.lastValue = specializationSelect.value;
        }

        specializationSelect.value = 'Chưa chọn chuyên ngành';
        specializationSelect.disabled = true;
        specializationHint.textContent = 'Sinh viên học kỳ 1 đến 3 chưa được chọn chuyên ngành.';
    } else {
        specializationSelect.disabled = false;
        specializationHint.textContent = 'Sinh viên từ học kỳ 4 trở đi có thể chọn chuyên ngành từ danh sách có sẵn.';
        if (!majorSelect.value) {
            specializationSelect.value = '';
        } else if (specializationSelect.value === 'Chưa chọn chuyên ngành' && specializationSelect.dataset.lastValue) {
            specializationSelect.value = specializationSelect.dataset.lastValue;
        }
    }
}

function renderCourseOptions(courses) {
    courseSelect.innerHTML = '';

    if (!courses.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Không tìm thấy môn học phù hợp';
        courseSelect.appendChild(option);
        selectedCourseInfo.textContent = 'Không có dữ liệu môn học để hiển thị.';
        return;
    }

    courses.forEach(course => {
        const option = document.createElement('option');
        option.value = course.code;
        option.textContent = `${course.code} - ${course.name}`;
        courseSelect.appendChild(option);
    });

    updateSelectedCourseInfo();
}

function filterCourseOptions() {
    const keyword = courseSearch.value.trim().toLowerCase();
    displayedCourses = courseCatalog.filter(course => {
        const haystack = `${course.code} ${course.name}`.toLowerCase();
        return haystack.includes(keyword);
    });
    renderCourseOptions(displayedCourses);
}

function updateSelectedCourseInfo() {
    const selectedCode = courseSelect.value;
    const selectedCourse = displayedCourses.find(course => course.code === selectedCode)
        || courseCatalog.find(course => course.code === selectedCode);

    if (!selectedCourse) {
        selectedCourseInfo.textContent = 'Chọn môn học để xem thông tin tín chỉ.';
        return;
    }

    selectedCourseInfo.textContent = `${selectedCourse.code} - ${selectedCourse.name} | ${selectedCourse.credits} tín chỉ`;
}

function openCourseModal() {
    hideCreateMessages();
    courseSearch.value = '';
    displayedCourses = [...courseCatalog];
    renderCourseOptions(displayedCourses);
    courseGrade.value = '';
    courseGrade.disabled = false;
    courseStatusSelect.value = 'auto';
    courseModalBackdrop.style.display = 'block';
}

function closeCourseModal() {
    courseModalBackdrop.style.display = 'none';
}

function saveCourseFromModal() {
    const code = courseSelect.value;
    const course = courseCatalog.find(item => item.code === code);
    const currentSemesterValue = Number(document.getElementById('currentSemester')?.value) || 0;

    if (!course) {
        showCreateError('Vui lòng chọn môn học hợp lệ');
        return;
    }

    // Tính toán điểm và trạng thái mới trước
    const statusVal = courseStatusSelect.value;
    let grade = 0.0;
    let finalStatus = '';

    if (statusVal === 'Không tính điểm' || statusVal === 'Miễn' || statusVal === 'Đạt') {
        grade = statusVal === 'Đạt' ? 5.0 : 0.0;
        finalStatus = statusVal;
    } else {
        grade = Number(courseGrade.value);
        if (courseGrade.value.trim() === '' || Number.isNaN(grade) || grade < 0 || grade > 10) {
            showCreateError('Điểm môn học phải nằm trong khoảng 0-10');
            return;
        }
        finalStatus = grade >= 5 ? 'Đạt' : 'Chưa đạt';
    }

    const newCourseData = {
        code: course.code,
        name: course.name,
        credits: Number(course.credits) || 0,
        grade: grade,
        status: finalStatus,
        gradeSpecified: statusVal === 'auto',
        semesterTaken: currentSemesterValue,
        attemptNumber: 1,
    };

    // Kiểm tra môn đã tồn tại → hiện modal xác nhận
    const existingOccurrences = studentCourses.filter(item => item.code === code);
    if (existingOccurrences.length > 0) {
        const lastExisting = existingOccurrences[existingOccurrences.length - 1];
        newCourseData.attemptNumber = existingOccurrences.length + 1; // số lần mới nếu thêm
        pendingGradeChange = {
            lastExisting,
            existingCount: existingOccurrences.length,
            newData: newCourseData,
        };
        showGradeChangeModal(lastExisting, newCourseData);
        return;
    }

    // Môn mới → thêm trực tiếp
    addCourseAndReset(newCourseData, `Đã thêm môn ${course.name || course.code} thành công!`);
}

function showGradeChangeModal(existing, newData) {
    try {
        console.log("showGradeChangeModal starting...", existing, newData);
        const comparison = document.getElementById('gradeChangeComparison');

        let oldGradeDisplay = formatGrade(existing.grade);
        if (['Miễn', 'Không tính điểm'].includes(existing.status)) {
            oldGradeDisplay = existing.status;
        } else if (existing.status === 'Đạt' && (!existing.gradeSpecified || existing.grade === 0 || existing.grade === 0.0 || existing.grade === "0" || existing.grade === "0.0")) {
            oldGradeDisplay = 'Điểm đạt';
        }

        let newGradeDisplay = formatGrade(newData.grade);
        if (['Miễn', 'Không tính điểm'].includes(newData.status)) {
            newGradeDisplay = newData.status;
        } else if (newData.status === 'Đạt' && (!newData.gradeSpecified || newData.grade === 0 || newData.grade === 0.0 || newData.grade === "0" || newData.grade === "0.0")) {
            newGradeDisplay = 'Điểm đạt';
        }

        const isOldPassed = ['Đạt', 'Miễn', 'Không tính điểm'].includes(existing.status);
        const isNewPassed = ['Đạt', 'Miễn', 'Không tính điểm'].includes(newData.status);

        const oldColorClass = isOldPassed ? 'pass' : 'fail';
        const newColorClass = isNewPassed ? 'pass' : 'fail';

        comparison.innerHTML = `
            <div class="grade-change-course-name">${newData.code} - ${newData.name}</div>
            <div class="grade-change-row">
                <span class="grade-change-label">Điểm môn học</span>
                <div class="grade-change-values">
                    <span class="grade-badge ${oldColorClass} old">${oldGradeDisplay}</span>
                    <span class="grade-arrow">→</span>
                    <span class="grade-badge ${newColorClass}">${newGradeDisplay}</span>
                </div>
            </div>
            <div class="grade-change-row">
                <span class="grade-change-label">Trạng thái</span>
                <div class="grade-change-values">
                    <span class="grade-badge ${oldColorClass}">${existing.status}</span>
                    <span class="grade-arrow">→</span>
                    <span class="grade-badge ${newColorClass}">${newData.status}</span>
                </div>
            </div>
        `;

        document.getElementById('gradeChangeModalBackdrop').style.display = 'block';
        console.log("showGradeChangeModal displayed successfully");
    } catch (e) {
        console.error("Error in showGradeChangeModal:", e);
    }
}

function confirmGradeChange() {
    if (!pendingGradeChange) return;

    const { lastExisting, existingCount, newData } = pendingGradeChange;
    // Tìm và thay thế lần học cuối cùng của môn này
    let lastIdx = -1;
    for (let i = studentCourses.length - 1; i >= 0; i--) {
        if (studentCourses[i].code === newData.code) {
            lastIdx = i;
            break;
        }
    }
    if (lastIdx !== -1) {
        // Giữ nguyên attemptNumber và semesterTaken cũ nếu không có giá trị mới
        newData.attemptNumber = studentCourses[lastIdx].attemptNumber || existingCount;
        newData.semesterTaken = newData.semesterTaken || studentCourses[lastIdx].semesterTaken || 0;
        studentCourses[lastIdx] = newData;
    }

    pendingGradeChange = null;
    document.getElementById('gradeChangeModalBackdrop').style.display = 'none';

    renderCourseTable();
    hideCreateMessages();
    showToast(`Đã cập nhật điểm môn ${newData.code} thành công!`, 'success');

    resetCourseModalInputs();
}

function addNewAttempt() {
    if (!pendingGradeChange) return;

    const { existingCount, newData } = pendingGradeChange;
    newData.attemptNumber = existingCount + 1;
    studentCourses.push(newData);

    pendingGradeChange = null;
    document.getElementById('gradeChangeModalBackdrop').style.display = 'none';

    renderCourseTable();
    hideCreateMessages();
    showToast(`Đã thêm lần học ${newData.attemptNumber} của môn ${newData.code} thành công!`, 'success');

    resetCourseModalInputs();
}

function cancelGradeChange() {
    pendingGradeChange = null;
    document.getElementById('gradeChangeModalBackdrop').style.display = 'none';
}

function addCourseAndReset(courseData, message) {
    studentCourses.push(courseData);
    renderCourseTable();
    hideCreateMessages();
    showToast(message, 'success');
    resetCourseModalInputs();
}

function resetCourseModalInputs() {
    courseGrade.value = '';
    courseGrade.disabled = false;
    courseStatusSelect.value = 'auto';
    courseSearch.value = '';
    filterCourseOptions();
    courseSearch.focus();
}

function renderCourseTable() {
    tableBody.innerHTML = '';

    if (!studentCourses.length) {
        tableWrap.style.display = 'none';
        emptyState.style.display = 'block';
    } else {
        tableWrap.style.display = 'block';
        emptyState.style.display = 'none';
    }

    // Sắp xếp: theo mã môn, rồi theo lần học
    studentCourses.sort((a, b) => {
        if (a.code !== b.code) return a.code.localeCompare(b.code);
        return (a.attemptNumber || 1) - (b.attemptNumber || 1);
    });
    saveDraft();

    studentCourses.forEach((course, index) => {
        const isPassed = ['Đạt', 'Miễn', 'Không tính điểm'].includes(course.status);
        let statusClass = 'failed';
        if (isPassed) {
            statusClass = 'passed';
        }

        let gradeDisplay = formatGrade(course.grade);
        if (course.status === 'Không tính điểm' || course.status === 'Miễn') {
            gradeDisplay = course.status;
        } else if (course.status === 'Đạt' && (!course.gradeSpecified || course.grade === 0 || course.grade === 0.0 || course.grade === "0" || course.grade === "0.0")) {
            gradeDisplay = 'Điểm đạt';
        }
        const attemptDisplay = course.attemptNumber || 1;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${course.code}</strong></td>
            <td>${course.name}</td>
            <td>${course.credits}</td>
            <td>${attemptDisplay}</td>
            <td>${gradeDisplay}</td>
            <td><span class="status-pill ${statusClass}">${course.status}</span></td>
            <td><button type="button" class="btn btn-secondary remove-course-btn" data-code="${course.code}" data-attempt="${attemptDisplay}">Xóa</button></td>
        `;
        tableBody.appendChild(row);
    });

    tableBody.querySelectorAll('button.remove-course-btn').forEach(button => {
        button.addEventListener('click', () => removeAttempt(button.dataset.code, parseInt(button.dataset.attempt)));
    });

    updateCreditSummary();
}

function updateCreditSummary() {
    // Gom theo mã môn để tránh tính trùng lần học lại
    const courseSummaryMap = {};
    studentCourses.forEach(course => {
        const key = course.code;
        if (!courseSummaryMap[key]) {
            courseSummaryMap[key] = {
                code: course.code,
                name: course.name,
                hasPassed: false,
                bestGrade: null,
                credits: course.credits,
                gradeSpecified: false
            };
        }
        const entry = courseSummaryMap[key];
        const isPassed = ['Đạt', 'Miễn', 'Không tính điểm'].includes(course.status);
        if (isPassed) {
            entry.hasPassed = true;
            if (course.gradeSpecified !== false && course.status === 'Đạt') {
                const g = parseFloat(course.grade);
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
    const passedCount = passedCourses.length;
    // Số lần học (không phải số môn) chưa qua
    const failedAttempts = studentCourses.filter(
        c => !['Đạt', 'Miễn', 'Không tính điểm'].includes(c.status)
    ).length;

    // GPA: lấy điểm cao nhất của mỗi môn đã qua
    let totalGradePoints = 0;
    let totalCreditsForGpa = 0;
    passedCourses.forEach(c => {
        if (isNonAccumulatedCourse(c.code, c.name)) {
            return;
        }
        if (c.gradeSpecified && c.bestGrade !== null) {
            const credits = parseInt(c.credits) || 0;
            if (credits > 0) {
                totalGradePoints += c.bestGrade * credits;
                totalCreditsForGpa += credits;
            }
        }
    });
    const gpa = totalCreditsForGpa > 0 ? (totalGradePoints / totalCreditsForGpa).toFixed(2) : '0.00';

    document.getElementById('accumulatedCreditsValue').textContent = accumulatedCredits;
    document.getElementById('totalCoursesValue').textContent = studentCourses.length;
    document.getElementById('courseStatusValue').textContent = `${passedCount} / ${failedAttempts}`;

    const gpaValEl = document.getElementById('gpaValue');
    if (gpaValEl) {
        gpaValEl.textContent = gpa;
    }
}

function removeAttempt(code, attemptNum) {
    const idx = studentCourses.findIndex(
        c => c.code === code && (c.attemptNumber || 1) === attemptNum
    );
    if (idx !== -1) {
        studentCourses.splice(idx, 1);
    }
    renderCourseTable();
}

async function submitCreateStudentForm(event) {
    event.preventDefault();
    hideCreateMessages();

    let studentIdInput = document.getElementById('studentId');
    if (typeof EDIT_MODE_ID !== 'undefined' && !EDIT_MODE_ID && !studentIdInput.value.trim()) {
        await populateNextStudentId();
    }

    if (!validateCreateStudentForm()) {
        return;
    }

    const payload = {
        student_id: document.getElementById('studentId').value.trim(),
        name: document.getElementById('studentName').value.trim(),
        year_admitted: Number(document.getElementById('yearAdmitted').value),
        current_semester: Number(document.getElementById('currentSemester').value),
        major: document.getElementById('major').value.trim(),
        specialization: specializationSelect.disabled
            ? 'Chưa chọn chuyên ngành'
            : (specializationSelect.value || 'Chưa chọn chuyên ngành'),
        study_goal: document.getElementById('studyGoal').value,
        academic_class: academicClassSelect.value.trim(),
        courses: studentCourses.map(course => ({
            code: course.code,
            grade: course.grade,
            status: course.status,
            grade_specified: course.gradeSpecified,
            semester_taken: course.semesterTaken || Number(document.getElementById('currentSemester').value),
            attempt_number: course.attemptNumber || 1,
        })),
    };

    try {
        const url = (typeof EDIT_MODE_ID !== 'undefined' && EDIT_MODE_ID) ? `/api/students/${EDIT_MODE_ID}` : '/api/students';
        const method = (typeof EDIT_MODE_ID !== 'undefined' && EDIT_MODE_ID) ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Không lưu được sinh viên');
        }

        showToast(`${result.message}`, 'success');
        localStorage.removeItem(getDraftKey());
        document.dispatchEvent(new CustomEvent("form-drafts:clear", { detail: { form: createForm } }));
        
        // Xóa state cũ trong sessionStorage vì dữ liệu sinh viên đã thay đổi
        sessionStorage.removeItem('studentPageState');
        sessionStorage.removeItem('shouldRestore');
        
        if (typeof EDIT_MODE_ID !== 'undefined' && EDIT_MODE_ID) {
            setTimeout(() => {
                window.location.href = `/students/${EDIT_MODE_ID}/course-history`;
            }, 1000);
        } else {
            resetCreateStudentForm(false);
        }
    } catch (error) {
        showCreateError(error.message);
    }
}

function resetCreateStudentForm(clearSuccess = true) {
    createForm.reset();
    document.getElementById('studyGoal').value = 'đúng hạn';
    document.getElementById('yearAdmitted').value = '';
    document.getElementById('currentSemester').value = '';
    document.getElementById('major').value = '';
    academicClassSelect.value = '';
    loadSpecializations('');
    studentCourses = [];
    renderCourseTable();
    updateSpecializationState();
    clearAllFieldErrors();
}

function hideCreateMessages() {
    return;
}

// Giả sử có định nghĩa hàm showToast, showCreateError, formatGrade ở môi trường base.html hoặc định nghĩa ở đây nếu chưa có
if (typeof showToast === 'undefined') {
    window.showToast = function(msg, type) {
        console.log(`[Toast ${type}]: ${msg}`);
    }
}

function showCreateError(message) {
    showToast(message, 'error');
}

function formatGrade(value) {
    return Number(value).toFixed(1);
}

function validateCreateStudentForm() {
    clearAllFieldErrors();

    const studentId = document.getElementById('studentId').value.trim();
    const studentName = document.getElementById('studentName').value.trim();
    const yearAdmitted = Number(document.getElementById('yearAdmitted').value);
    const currentSemester = Number(document.getElementById('currentSemester').value);
    const major = document.getElementById('major').value.trim();
    const specialization = specializationSelect.value;
    const academicClass = academicClassSelect.value.trim();

    const validations = [
        {
            fieldId: 'studentId',
            valid: Boolean(studentId),
            message: 'Vui lòng nhập mã sinh viên.',
        },
        {
            fieldId: 'studentName',
            valid: Boolean(studentName),
            message: 'Vui lòng nhập tên sinh viên.',
        },
        {
            fieldId: 'yearAdmitted',
            valid: Number.isFinite(yearAdmitted) && yearAdmitted >= 2000 && yearAdmitted <= 2030,
            message: 'Năm vào học phải trong khoảng 2000 đến 2030.',
        },
        {
            fieldId: 'currentSemester',
            valid: Number.isFinite(currentSemester) && currentSemester >= 1 && currentSemester <= 8,
            message: 'Học kỳ hiện tại phải từ 1 đến 8.',
        },
        {
            fieldId: 'major',
            valid: Boolean(major),
            message: 'Vui lòng chọn ngành học.',
        },
        {
            fieldId: 'specialization',
            valid: currentSemester < 4 ? specialization === 'Chưa chọn chuyên ngành' : Boolean(specialization) && specialization !== 'Chưa chọn chuyên ngành',
            message: currentSemester < 4
                ? 'Học kỳ 1 đến 3 chưa được chọn chuyên ngành.'
                : 'Vui lòng chọn chuyên ngành.',
        },
        {
            fieldId: 'academicClass',
            valid: Boolean(academicClass),
            message: 'Vui lòng chọn lớp hành chính.',
        },
    ];

    const firstInvalid = validations.find(item => !item.valid);
    if (!firstInvalid) {
        return true;
    }

    setFieldError(firstInvalid.fieldId, firstInvalid.message);
    showToast(firstInvalid.message, 'warning');

    const field = document.getElementById(firstInvalid.fieldId);
    if (field) {
        field.focus();
        field.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    return false;
}

function setFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}Error`);
    if (field) {
        field.classList.add('input-invalid');
    }
    if (errorElement) {
        errorElement.textContent = message;
    }
}

function clearFieldError(fieldId) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}Error`);
    if (field) {
        field.classList.remove('input-invalid');
    }
    if (errorElement) {
        errorElement.textContent = '';
    }
}

function clearAllFieldErrors() {
    formFieldIds.forEach(clearFieldError);
}

function saveDraft() {
    const draft = {
        studentId: document.getElementById('studentId').value,
        studentName: document.getElementById('studentName').value,
        yearAdmitted: document.getElementById('yearAdmitted').value,
        currentSemester: document.getElementById('currentSemester').value,
        major: document.getElementById('major').value,
        specialization: document.getElementById('specialization').value,
        studyGoal: document.getElementById('studyGoal').value,
        academicClass: document.getElementById('academicClass').value,
        studentCourses: studentCourses
    };
    localStorage.setItem(getDraftKey(), JSON.stringify(draft));
}

function loadDraft() {
    const draftStr = localStorage.getItem(getDraftKey());
    if (!draftStr) return;
    try {
        const draft = JSON.parse(draftStr);
        if (draft.studentId) document.getElementById('studentId').value = draft.studentId;
        if (draft.studentName) document.getElementById('studentName').value = draft.studentName;
        if (draft.yearAdmitted) document.getElementById('yearAdmitted').value = draft.yearAdmitted;
        if (draft.currentSemester) document.getElementById('currentSemester').value = draft.currentSemester;
        if (draft.major) document.getElementById('major').value = draft.major;
        if (draft.specialization) document.getElementById('specialization').dataset.draftValue = draft.specialization;
        if (draft.studyGoal) document.getElementById('studyGoal').value = draft.studyGoal;
        if (draft.academicClass) document.getElementById('academicClass').value = draft.academicClass;
        if (Array.isArray(draft.studentCourses)) {
            studentCourses = draft.studentCourses;
        }
    } catch (e) {
        console.error('Lỗi khi tải bản nháp:', e);
    }
}

function getDraftKey() {
    return (typeof EDIT_MODE_ID !== 'undefined' && EDIT_MODE_ID)
        ? `editStudentDraft:${EDIT_MODE_ID}`
        : 'addStudentDraft';
}
