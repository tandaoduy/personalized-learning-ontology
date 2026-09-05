function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
         .toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
    document.body.dataset.activeRole = "student-plan";

    const container = document.getElementById("planPageContainer");
    const studentId = container.dataset.studentId;

    // UI Elements
    const btnGeneratePlan = document.getElementById("btnGeneratePlan");
    const btnWelcomeGenerate = document.querySelector("[data-trigger-generate]");
    const btnGenerateAlternative = document.getElementById("btnGenerateAlternative");
    const btnPrintPlan = document.getElementById("btnPrintPlan");
    const btnRetryPlan = document.getElementById("btnRetryPlan");
    const stateInitial = document.getElementById("planInitialState");
    const stateLoading = document.getElementById("planLoadingState");
    const stateError = document.getElementById("planErrorState");
    const errorMessage = document.getElementById("planErrorMessage");
    const planResultContainer = document.getElementById("planResultContainer");
    
    let currentPlanData = null;
    let currentPlans = [];
    let currentSelectedPlanIndex = 0;

    function showState(state) {
        if (state === "loading" && currentPlans.length > 0) {
            const overlay = document.getElementById("planOverlayLoader");
            if (overlay) overlay.style.display = "flex";
            return; // keep result visible
        }

        const overlay = document.getElementById("planOverlayLoader");
        if (overlay) overlay.style.display = "none";

        stateInitial.classList.add("hidden");
        stateLoading.classList.add("hidden");
        stateError.classList.add("hidden");
        planResultContainer.classList.add("hidden");
        btnPrintPlan.disabled = true;
        btnGenerateAlternative.disabled = true;

        if (state === "initial") stateInitial.classList.remove("hidden");
        if (state === "loading") stateLoading.classList.remove("hidden");
        if (state === "error") stateError.classList.remove("hidden");
        if (state === "result") {
            planResultContainer.classList.remove("hidden");
            btnPrintPlan.disabled = false;
            btnGenerateAlternative.disabled = false;
        }
    }

    function generatePlan(randomize = false) {
        if (!studentId) {
            showError("Không tìm thấy mã sinh viên.");
            return;
        }

        showState("loading");
        
        let payload = { student_id: studentId };
        if (randomize) {
            payload.randomize = true;
        }

        fetch("/api/recommendations", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                if (data.data.plans) {
                    currentPlans = data.data.plans;
                } else {
                    currentPlans = [data.data]; // fallback
                }
                currentSelectedPlanIndex = 0;
                
                renderPlanDetail(currentSelectedPlanIndex);
                
                showState("result");
                if (window.UIComponents) {
                    window.UIComponents.showAlert("Kế hoạch học tập đã được tạo thành công!", {type: "success"});
                }
            } else {
                showError(data.error || "Có lỗi không xác định từ máy chủ.");
            }
        })
        .catch(err => {
            console.error("Lỗi khi sinh kế hoạch:", err);
            if (err.name === 'TypeError' && err.message !== 'Failed to fetch') {
                showError("Lỗi xử lý dữ liệu trình duyệt: " + err.message);
            } else {
                showError("Không thể kết nối đến máy chủ. Vui lòng thử lại sau.");
            }
        });
    }



    function showError(msg) {
        errorMessage.textContent = msg;
        showState("error");
    }

    function formatReasonSentence(reasons) {
        if (!reasons || reasons.length === 0) return "-";
        let text = reasons.join(", ");
        text = text.replace(/môn/gi, "học phần");
        text = text.charAt(0).toUpperCase() + text.slice(1);
        if (!text.endsWith('.')) {
            text += '.';
        }
        return text;
    }

    function getStatusHtml(course, nextSem) {
        if (course.is_retake) {
            return `<span class="status-badge status-retake">Học lại</span>`;
        } else if (course.recommended_semester) {
            if (nextSem && course.recommended_semester < nextSem) {
                return `<span class="status-badge status-delayed">Kỳ ${course.recommended_semester}</span>`;
            }
            return `<span class="status-badge status-semester">Kỳ ${course.recommended_semester}</span>`;
        }
        return `<span class="status-badge status-semester">Mở rộng</span>`;
    }

    function sortCourses(courses, nextSemester) {
        if (!courses) return [];
        return [...courses].sort((a, b) => {
            const scoreA = a.total_priority_score || 0;
            const scoreB = b.total_priority_score || 0;
            if (scoreA !== scoreB) {
                return scoreB - scoreA; // Giảm dần
            }
            // Nếu cùng độ ưu tiên, sắp xếp theo mã môn
            return (a.code || "").localeCompare(b.code || "");
        });
    }

    window.showExcludedCoursesByRule = function(rule) {
        const section = document.getElementById('excludedCoursesSection');
        const tbody = document.getElementById('excludedCoursesList');
        const detail = document.getElementById('excludedCoursesDetail');
        const detailHint = document.getElementById('excludedDetailHint');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!section || !tbody || !detail || !detailHint || !toggleBtn || !summaryGrid) return;

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

        const detailList = list
            .filter(course => ((course.failed_rules || [])[0] || 'other') === rule)
            .sort((a, b) => (a.code || "").localeCompare(b.code || ""));
            
        tbody.innerHTML = '';
        detailList.forEach((course, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="text-align: center; vertical-align: middle;">${index + 1}</td>
                <td class="font-bold" style="text-align: center; vertical-align: middle;">${escapeHtml(course.code || '-')}</td>
                <td style="vertical-align: middle;">${escapeHtml(course.name || '-')}</td>
                <td style="vertical-align: middle;">${escapeHtml((course.reasons || []).join(', ') || '-')}</td>
            `;
            tbody.appendChild(row);
        });

        // Update chips styling
        summaryGrid.querySelectorAll('.ui-chip').forEach(chip => {
            chip.classList.toggle('is-active', chip.dataset.rule === rule);
        });
        section.dataset.selectedRule = rule;
        detail.style.display = 'block';
        detailHint.style.display = 'block';
        detailHint.textContent = `${ruleMeta[rule] || rule}: ${detailList.length} học phần`;
        toggleBtn.style.display = 'inline-block';
        toggleBtn.textContent = 'Ẩn chi tiết';
    };

    window.toggleExcludedCoursesDetail = function() {
        const detail = document.getElementById('excludedCoursesDetail');
        const toggleBtn = document.getElementById('toggleExcludedCoursesBtn');
        const detailHint = document.getElementById('excludedDetailHint');
        const section = document.getElementById('excludedCoursesSection');
        const summaryGrid = document.getElementById('excludedSummaryGrid');
        if (!detail || !toggleBtn || !detailHint || !section || !summaryGrid) return;

        detail.style.display = 'none';
        detailHint.style.display = 'none';
        toggleBtn.style.display = 'none';
        section.dataset.selectedRule = '';
        summaryGrid.querySelectorAll('.ui-chip').forEach(chip => {
            chip.classList.remove('is-active');
        });
    };

    function renderExcludedCourses(courses) {
        const section = document.getElementById('excludedCoursesSection');
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
            section.style.display = 'block';
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
                <button type="button" class="ui-chip ui-chip--${meta.className}" data-rule="${escapeHtml(rule)}" onclick="showExcludedCoursesByRule('${escapeHtml(rule)}')">
                    ${escapeHtml(meta.label)} <span class="ui-chip__count">${count}</span>
                </button>
            `;
        }).join('');

        empty.style.display = 'none';
        toggleBtn.style.display = 'none';
        section.style.display = 'block';
    }

    function renderPlanDetail(index) {
        const data = currentPlans[index];
        if (!data) return;
        currentPlanData = data; // for backward compatibility

        // 1. Thống kê (Summary Cards)
        document.getElementById("summaryCount").textContent = data.recommended_courses ? data.recommended_courses.length : 0;
        document.getElementById("summaryCredits").textContent = data.total_recommended_credits || 0;
        document.getElementById("summarySemester").textContent = data.next_semester || 0;
        document.getElementById("opt1Credits").textContent = data.total_recommended_credits || 0;

        // Sắp xếp dữ liệu trước khi render
        const nextSem = data.next_semester || 99;
        const sortedRecommended = sortCourses(data.recommended_courses, nextSem);
        const sortedEligible = sortCourses(data.eligible_courses, nextSem);
        
        // Print Summary Text
        let countRetake = 0;
        let countCompulsory = 0;
        sortedRecommended.forEach(course => {
            if (course.is_retake) countRetake++;
            let r_list = course.reasons;
            if (typeof r_list === 'string') r_list = [r_list];
            if (Array.isArray(r_list) && r_list.some(r => r && r.toLowerCase().includes("bắt buộc"))) {
                countCompulsory++;
            }
        });
        
        const printSummary = document.getElementById("printSummaryText");
        if (printSummary) {
            printSummary.innerHTML = `
                <ul style="margin-bottom: 16px; padding-left: 24px; list-style-type: disc; line-height: 1.8;">
                    <li><strong>Học kì đề xuất:</strong> ${nextSem === 99 ? '-' : nextSem}</li>
                    <li><strong>Tổng số môn gợi ý:</strong> ${sortedRecommended.length} môn</li>
                    <li><strong>Tổng số tín chỉ:</strong> ${data.total_recommended_credits || 0} tín chỉ</li>
                    <li><strong>Học phần bắt buộc:</strong> ${countCompulsory}</li>
                    <li><strong>Học phần học lại:</strong> ${countRetake}</li>
                </ul>
            `;
        }

        // 2. Danh sách được gợi ý (Bảng)
        const recTbody = document.getElementById("recommendedTableBody");
        recTbody.innerHTML = "";
        const expGrid = document.getElementById("explanationGrid");
        expGrid.innerHTML = "";
        
        if (sortedRecommended.length > 0) {
            sortedRecommended.forEach((course, index) => {
                if (course.recommended_semester && nextSem && course.recommended_semester < nextSem) {
                    if (!course.reasons) course.reasons = [];
                    if (!course.reasons.includes("Môn bị trễ so với học kỳ khuyến nghị")) {
                        course.reasons.push("Môn bị trễ so với học kỳ khuyến nghị");
                    }
                }
                
                // Render Table Row
                const tr = document.createElement("tr");
                const statusHtml = getStatusHtml(course, nextSem);
                const reasonsText = formatReasonSentence(course.reasons);
                
                let formattedBadges = (course.reasons || []).map(r => r.replace(/môn/gi, 'học phần'));
                const reasonsBadges = formattedBadges.map(r => `<span class="reason-badge">${escapeHtml(r)}</span>`).join("");
                
                tr.innerHTML = `
                    <td style="text-align: center; vertical-align: middle;">${index + 1}</td>
                    <td class="font-bold" style="text-align: center; vertical-align: middle;">
                        ${escapeHtml(course.code)}
                        <button class="no-print" onclick="window.openPrerequisiteModal('${escapeHtml(course.code)}')" style="border:none; background:none; cursor:pointer; color:#3b82f6; margin-left:4px;" title="Xem chuỗi môn học">🔗</button>
                    </td>
                    <td style="vertical-align: middle;">${escapeHtml(course.name)}</td>
                    <td style="text-align: center; vertical-align: middle;">${course.credits}</td>
                    <td style="text-align: center; vertical-align: middle;">${statusHtml}</td>
                    <td style="vertical-align: middle;">${escapeHtml(reasonsText) || "-"}</td>
                `;
                recTbody.appendChild(tr);

                // Render Explanation Card
                const card = document.createElement("div");
                card.className = "exp-card";
                card.innerHTML = `
                    <div class="exp-card-header">
                        <span class="exp-code">${escapeHtml(course.code)}</span>
                        <span class="exp-name" title="${escapeHtml(course.name)}">${escapeHtml(course.name)}</span>
                        <span class="exp-credits">${course.credits} TC</span>
                    </div>
                    <div class="exp-meta">
                        ${statusHtml}
                        <div class="exp-score"><span class="exp-score-label">Điểm ưu tiên:</span> ${Math.round(course.total_priority_score ?? course.heuristic_score ?? 0)}</div>
                    </div>
                    <div class="exp-reasons-title">Lý do chọn:</div>
                    <div class="exp-reasons-container">${reasonsBadges || "-"}</div>
                `;
                expGrid.appendChild(card);
            });
        } else {
            recTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Không có môn học nào được gợi ý.</td></tr>`;
            expGrid.innerHTML = `<div class="text-muted">Không có dữ liệu.</div>`;
        }

        // Bỏ render Phân tích độ khó theo yêu cầu
        const difficultyContainer = document.getElementById("difficultyAnalysisContainer");
        if (difficultyContainer) {
            difficultyContainer.style.display = 'none';
            difficultyContainer.innerHTML = '';
        }

        // 3. Danh sách môn đủ điều kiện học (Bảng)
        const eliTbody = document.getElementById("eligibleTableBody");
        eliTbody.innerHTML = "";
        
        if (sortedEligible.length > 0) {
            document.getElementById("eligibleCountText").textContent = sortedEligible.length;
            sortedEligible.forEach((course, index) => {
                if (course.recommended_semester && nextSem && course.recommended_semester < nextSem) {
                    if (!course.reasons) course.reasons = [];
                    if (!course.reasons.includes("Môn bị trễ so với học kỳ khuyến nghị")) {
                        course.reasons.push("Môn bị trễ so với học kỳ khuyến nghị");
                    }
                }
                
                const tr = document.createElement("tr");
                const statusHtml = getStatusHtml(course, nextSem);
                const reasonsText = formatReasonSentence(course.reasons);
                
                tr.innerHTML = `
                    <td style="text-align: center; vertical-align: middle;">${index + 1}</td>
                    <td class="font-bold" style="text-align: center; vertical-align: middle;">
                        ${escapeHtml(course.code)}
                        <button class="no-print" onclick="window.openPrerequisiteModal('${escapeHtml(course.code)}')" style="border:none; background:none; cursor:pointer; color:#3b82f6; margin-left:4px;" title="Xem chuỗi môn học">🔗</button>
                    </td>
                    <td style="vertical-align: middle;">${escapeHtml(course.name)}</td>
                    <td style="text-align: center; vertical-align: middle;">${course.credits}</td>
                    <td style="text-align: center; vertical-align: middle;">${statusHtml}</td>
                    <td style="vertical-align: middle;">${escapeHtml(reasonsText) || "-"}</td>
                `;
                eliTbody.appendChild(tr);
            });
        } else {
            document.getElementById("eligibleCountText").textContent = "0";
            eliTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Không có môn học nào đủ điều kiện đăng ký trong lúc này.</td></tr>`;
        }

        // 4. Danh sách môn bị loại (Render bằng hàm mới)
        if (data.excluded_courses) {
            renderExcludedCourses(data.excluded_courses);
        } else {
            const excludedSection = document.getElementById('excludedCoursesSection');
            if (excludedSection) excludedSection.style.display = 'none';
        }

        // Print Date (Removed)
        // const today = new Date();
        // const dateStr = `Ngày ${today.getDate().toString().padStart(2, '0')} tháng ${(today.getMonth() + 1).toString().padStart(2, '0')} năm ${today.getFullYear()}`;
        // document.getElementById("printDateString").innerHTML = `<i>${dateStr}</i>`;
    }

    // Modal Logic
    const modals = {
        compare: document.getElementById("compareModal")
    };

    function openModal(id) {
        if(modals[id]) modals[id].classList.remove("hidden");
    }

    function closeModal(id) {
        if(modals[id]) modals[id].classList.add("hidden");
    }

    // Event Listeners
    btnGeneratePlan.addEventListener("click", () => generatePlan(false));
    btnWelcomeGenerate?.addEventListener("click", () => btnGeneratePlan.click());
    btnRetryPlan.addEventListener("click", () => generatePlan(false));

    btnGenerateAlternative.addEventListener("click", () => {
        if (!currentPlanData) {
            if(window.UIComponents) window.UIComponents.showAlert("Vui lòng sinh kế hoạch trước.", {type: "warning"});
            return;
        }
        generatePlan(true);
    });

    btnPrintPlan.addEventListener("click", () => {
        window.print();
    });

    // Auto-generate on load
    // if (studentId) {
    //     generatePlan();
    // }
});

// Modal Chuỗi tiên quyết (Global Scope)
window.closePrerequisiteModal = function() {
    const modal = document.getElementById("prerequisiteModal");
    if(modal) modal.style.display = 'none';
};

window.openPrerequisiteModal = function(courseCode) {
    const modal = document.getElementById("prerequisiteModal");
    const body = document.getElementById("prerequisiteModalBody");
    const container = document.getElementById("planPageContainer");
    const studentId = container ? container.dataset.studentId : null;
    if(!modal || !body || !studentId) return;

    modal.style.display = 'flex';
    body.innerHTML = `<div style="text-align: center; padding: 20px; color: #6b7280;">Đang phân tích đồ thị môn học...</div>`;

    fetch(`/api/courses/${courseCode}/prerequisite-chain?student_id=${studentId}`)
        .then(r => r.json())
        .then(res => {
            if(res.success && res.data) {
                renderPrerequisiteTimeline(res.data, body);
            } else {
                body.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">Lỗi: ${res.error || 'Không thể lấy dữ liệu'}</div>`;
            }
        })
        .catch(err => {
            body.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">Lỗi kết nối máy chủ.</div>`;
        });
};

function renderPrerequisiteTimeline(data, container) {
    let html = `
        <div style="margin-bottom: 24px;">
            <h4 style="margin:0 0 12px 0; color: #111827; font-size: 16px;">Mục tiêu: <span style="color: #2563eb;">${escapeHtml(data.target_course.course_name)} (${escapeHtml(data.target_course.course_code)})</span></h4>
            <div style="font-size: 14px; padding: 12px 16px; background: #eff6ff; color: #1d4ed8; border-radius: 6px; border-left: 4px solid #3b82f6;">
                <strong>💡 Chỉ dẫn:</strong> ${escapeHtml(data.guidance)}
            </div>
        </div>
        <div class="timeline-container" style="position: relative; margin-left: 14px; padding-left: 24px; border-left: 2px solid #e5e7eb;">
    `;

    const statusColors = {
        'completed': { icon: '✅', color: '#059669', bg: '#ecfdf5', border: '#34d399' },
        'failed': { icon: '❌', color: '#dc2626', bg: '#fef2f2', border: '#f87171' },
        'available': { icon: '⭐', color: '#d97706', bg: '#fffbeb', border: '#fbbf24' },
        'locked': { icon: '🔒', color: '#4b5563', bg: '#f3f4f6', border: '#d1d5db' }
    };

    if (!data.prerequisite_chain || data.prerequisite_chain.length === 0) {
        container.innerHTML = html + `
            <div style="color: #6b7280; font-size: 14px;">Môn này không có môn tiên quyết hoặc cấu trúc đồ thị chưa được định nghĩa đầy đủ.</div>
        </div>`;
        return;
    }

    data.prerequisite_chain.forEach((item, index) => {
        const isTarget = item.course_code === data.target_course.course_code;
        const style = statusColors[item.status] || statusColors['locked'];
        const isCritical = item.course_code === data.critical_course;
        
        let highlightStyle = '';
        if (isTarget) {
            highlightStyle = 'box-shadow: 0 0 0 2px #fbbf24, 0 8px 16px rgba(245, 158, 11, 0.15); border-color: #fbbf24; transform: scale(1.02); z-index: 11;';
        } else if (isCritical) {
            highlightStyle = 'box-shadow: 0 0 0 2px #f87171, 0 4px 6px -1px rgba(0, 0, 0, 0.1);';
        }

        html += `
            <div class="timeline-item" style="position: relative; margin-bottom: ${index === data.prerequisite_chain.length - 1 ? '0' : '20px'};">
                <div class="timeline-dot" style="position: absolute; left: -36px; top: 12px; width: 22px; height: 22px; border-radius: 50%; background: white; border: 2px solid ${style.border}; display: flex; align-items: center; justify-content: center; font-size: 12px; z-index: 12;">
                    ${style.icon}
                </div>
                <div class="timeline-content" style="background: ${isTarget ? '#fffbf0' : style.bg}; border: 1px solid ${style.border}; border-radius: 8px; padding: 12px 16px; transition: all 0.2s; ${highlightStyle}">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                        <strong style="color: ${style.color}; font-size: 15px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                            <span>${escapeHtml(item.course_name)} (${escapeHtml(item.course_code)})</span>
                            ${isTarget ? '<span style="font-size: 11px; padding: 3px 8px; border-radius: 999px; background: linear-gradient(135deg, #f59e0b, #ea580c); color: white; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(234, 88, 12, 0.3);">⭐ Mục tiêu</span>' : ''}
                        </strong>
                        <span style="font-size: 12px; background: white; padding: 2px 6px; border-radius: 4px; border: 1px solid #e5e7eb; white-space: nowrap; margin-left: 8px;">${item.credits} TC</span>
                    </div>
                    <div style="font-size: 13px; color: ${style.color}; font-weight: 500;">
                        Trạng thái: ${escapeHtml(item.message)}
                    </div>
                    ${item.prerequisites && item.prerequisites.length > 0 ? `<div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Tiên quyết: ${escapeHtml(item.prerequisites.join(', '))}</div>` : ''}
                </div>
            </div>
        `;
    });

    html += `</div>`;
    container.innerHTML = html;
}
