document.addEventListener("DOMContentLoaded", async () => {
    document.body.dataset.activeRole = "student";

    const progressDashboard = document.getElementById("progressDashboard");
    if (!progressDashboard) return;

    const studentId = progressDashboard.dataset.studentId;
    if (!studentId) return;

    try {
        const initialStudent = JSON.parse(document.getElementById("initialDashboardStudentData")?.textContent || "null");
        const initialCourses = JSON.parse(document.getElementById("initialDashboardCourseData")?.textContent || "[]");
        if (initialStudent && Array.isArray(initialCourses) && initialCourses.length) {
            renderProgress(initialStudent, initialCourses);
        }
    } catch (error) {
        console.warn("Initial dashboard data is unavailable:", error);
    }

    try {
        // Fetch student data and course catalog concurrently
        const [studentRes, coursesRes] = await Promise.all([
            fetch(`/api/students/${encodeURIComponent(studentId)}`),
            fetch("/api/students/courses")
        ]);

        const studentJson = await studentRes.json();
        const coursesJson = await coursesRes.json();

        if (studentJson.success && studentJson.data && coursesJson.success && coursesJson.data) {
            renderProgress(studentJson.data, coursesJson.data);
        }
    } catch (error) {
        console.error("Error fetching progress data:", error);
    }
});

function renderProgress(studentData, courseCatalog) {
    const attempts = studentData.course_attempts || [];
    if (attempts.length === 0) return;

    // Create a map of course codes to their credit values
    const courseCredits = {};
    courseCatalog.forEach(course => {
        if (course.code) {
            courseCredits[course.code] = Number(course.credits) || 0;
        }
    });

    const courseSummaryMap = {};
    const NON_ACCUMULATED_ENGLISH = ['FLS310', 'FLS312', 'FLS313'];
    const NON_ACCUMULATED_FIXED = ['SOT301'];
    
    function isNonAccumulated(code, name = '') {
        const c = String(code).toUpperCase();
        const n = String(name).toLowerCase();
        if (NON_ACCUMULATED_ENGLISH.includes(c) || NON_ACCUMULATED_FIXED.includes(c)) return true;
        if (n.includes('giáo dục thể chất')) return true;
        return false;
    }

    // Process attempts to find best status per course
    attempts.forEach(attempt => {
        const code = attempt.course_code;
        if (!courseSummaryMap[code]) {
            courseSummaryMap[code] = {
                code: code,
                name: attempt.course_name,
                hasPassed: false,
                isFailed: false,
                isExempt: false,
                bestGrade: null,
                credits: courseCredits[code] || 0
            };
        }
        
        const entry = courseSummaryMap[code];
        const status = attempt.status;

        if (["Đạt", "Miễn", "Không tính điểm"].includes(status)) {
            entry.hasPassed = true;
            entry.isFailed = false; // Reset fail status if they passed eventually
            if (status === "Miễn" || status === "Không tính điểm") {
                entry.isExempt = true;
            }
            if (attempt.grade_specified && status === "Đạt") {
                const g = parseFloat(attempt.grade);
                if (!isNaN(g) && (entry.bestGrade === null || g > entry.bestGrade)) {
                    entry.bestGrade = g;
                }
            }
        } else if (status === "Chưa đạt" && !entry.hasPassed) {
            entry.isFailed = true;
        }
    });

    let passedCredits = 0;
    let failedCredits = 0;
    
    let totalGradePoints = 0;
    let totalCreditsForGpa = 0;

    Object.values(courseSummaryMap).forEach(course => {
        const isNonAcc = isNonAccumulated(course.code, course.name);
        
        if (course.hasPassed) {
            if (!isNonAcc) {
                passedCredits += course.credits;
                if (course.bestGrade !== null && course.credits > 0 && !course.isExempt) {
                    totalGradePoints += course.bestGrade * course.credits;
                    totalCreditsForGpa += course.credits;
                }
            }
        } else if (course.isFailed) {
            if (!isNonAcc) {
                failedCredits += course.credits;
            }
        }
    });

    const gpa = totalCreditsForGpa > 0 ? (totalGradePoints / totalCreditsForGpa).toFixed(2) : "0.00";

    // Update UI Stats
    document.getElementById("statPassedCredits").textContent = passedCredits;
    document.getElementById("statFailedCredits").textContent = failedCredits;
    document.getElementById("statGpa").textContent = gpa;

    // Estimate remaining credits (Typical bachelor is 132 credits)
    const TOTAL_ESTIMATED_CREDITS = 132;
    let remainingCredits = TOTAL_ESTIMATED_CREDITS - passedCredits;
    if (remainingCredits < 0) remainingCredits = 0;

    // Draw Chart
    const ctx = document.getElementById("progressChart");
    if (!ctx) return;

    // Destroy old chart if exists
    if (window.progressChartInstance) {
        window.progressChartInstance.destroy();
    }

    document.getElementById("chartCenterText").innerHTML = `
        <span class="chart-center-value">${passedCredits}</span>
        <span class="chart-center-label">TC Đã đạt</span>
    `;

    // Only draw if Chart.js is loaded
    if (typeof Chart !== 'undefined') {
        window.progressChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Đã đạt / Miễn', 'Chưa đạt', 'Chưa học'],
                datasets: [{
                    data: [passedCredits, failedCredits, remainingCredits],
                    backgroundColor: [
                        '#16a34a', // green-600
                        '#dc2626', // red-600
                        '#e2e8f0', // slate-200 (gray)
                    ],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: false // Hide legend to save space
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (passedCredits === 0 && failedCredits === 0) return 'Chưa có dữ liệu';
                                return ` ${context.label}: ${context.raw} tín chỉ`;
                            }
                        }
                    }
                }
            }
        });
    }
}
