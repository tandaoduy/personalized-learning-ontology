/**
 * JavaScript Quản trị học vụ - Phòng Đào tạo (Training Office)
 * Cung cấp đầy đủ tính năng: Quan hệ học phần hiện đại (Search, Smart Filter, Chip Tags, Visual Pipeline),
 * CTĐT, Phân công cố vấn hiện đại (KPIs, Batch Assign, Interactive Cards, Student Roster)
 */
(() => {
  const api = '/api/training-office';
  const state = {
    relations: [],
    courses: [],
    courseFormOptions: {},
    coursesLoaded: false,
    selectedCourse: null,
    originalSelectedCourse: null,
    editingPrereqs: [],
    editingCoreqs: [],
    relFilter: 'all',
    courseSearchQuery: '',
    programs: [],
    assignments: [],
    advisors: [],
    selectedClasses: new Set(),
    filterStatus: 'all',
    filterCohort: 'all',
    searchQuery: '',
    currentClass: null,
    currentTab: 'assign',
    rosterQuery: '',
    pendingRelationAction: null
  };

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = v => String(v ?? '').replace(/[&<>'"]/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[c]));

  const message = (text, type = 'success') => {
    if (window.showToast) {
      window.showToast(text, type);
    } else {
      alert(text);
    }
  };

  const refreshIcons = () => {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  };

  const confirmRelationChange = (title, description, confirmLabel, action, options = {}) => {
    const dialog = $('[data-confirm-relation-dialog]');
    if (!dialog) return;
    const isRemoval = options.isRemoval !== undefined ? options.isRemoval : title.toLowerCase().startsWith('xóa');
    const icon = $('[data-confirm-relation-icon]');
    if (icon) {
      icon.style.background = isRemoval ? '#fef2f2' : '#eff6ff';
      icon.style.color = isRemoval ? '#dc2626' : '#2563eb';
      icon.innerHTML = `<i data-lucide="${isRemoval ? 'trash-2' : 'plus-circle'}"></i>`;
    }
    const titleEl = $('[data-confirm-relation-title]');
    if (titleEl) titleEl.textContent = title;

    const descEl = $('[data-confirm-relation-description]');
    if (descEl) {
      let code = options.code;
      if (!code && typeof description === 'string') {
        const match = description.match(/(?:xóa|thêm)\s+([A-Z0-9_\-]+)/i) || description.match(/([A-Z0-9_\-]+)/);
        if (match) code = match[1];
      }
      const courseName = options.courseName || (code ? getCourseName(code) : '');

      let formattedHtml = '';
      if (code) {
        const actionVerb = isRemoval ? 'xóa' : 'thêm';
        const targetList = title.toLowerCase().includes('tiên quyết')
          ? 'học phần tiên quyết'
          : (title.toLowerCase().includes('song hành') ? 'học phần song hành' : 'danh sách quan hệ');
        const prep = isRemoval ? 'khỏi' : 'vào';

        formattedHtml = `
          <p class="to-confirm-msg">
            Bạn có chắc chắn muốn ${actionVerb} học phần <span class="to-confirm-code">${esc(code)}</span>${courseName ? ` <strong style="color:#0f172a;font-weight:600;">(${esc(courseName)})</strong>` : ''} ${prep} danh sách ${targetList}?
          </p>
          <div class="to-confirm-subtext ${isRemoval ? 'to-confirm-subtext--danger' : 'to-confirm-subtext--info'}">
            <i data-lucide="${isRemoval ? 'alert-triangle' : 'info'}"></i>
            <span>${isRemoval ? 'Ràng buộc này sẽ được gỡ bỏ khỏi mô hình tri thức (Ontology).' : 'Ràng buộc mới sẽ được cập nhật và kiểm tra vòng lặp phụ thuộc.'}</span>
          </div>
        `;
      } else {
        formattedHtml = `<p class="to-confirm-msg">${esc(description)}</p>`;
      }
      descEl.innerHTML = formattedHtml;
    }

    const submitBtn = $('[data-confirm-relation-submit]');
    if (submitBtn) {
      submitBtn.className = isRemoval ? 'to-btn to-btn--danger' : 'to-btn to-btn--primary';
      submitBtn.innerHTML = `
        <i data-lucide="${isRemoval ? 'trash-2' : 'check'}" style="width:16px;height:16px;"></i>
        <span>${esc(confirmLabel)}</span>
      `;
    }

    state.pendingRelationAction = action;
    dialog.showModal();
    refreshIcons();
  };

  // Helper tạo avatar initials
  const getInitials = (name) => {
    if (!name) return 'CV';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  // Helper format ngày giờ
  const formatDate = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return '';
    }
  };

  // HTTP Request Helper
  async function request(path, options = {}) {
    const response = await fetch(api + path, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      throw new Error(payload.error || 'Không thể xử lý yêu cầu.');
    }
    return payload.data;
  }

  const getCourseName = (code) => {
    const found = state.courses.find(c => c.code === code);
    return found ? (found.name || '') : '';
  };

  // =========================================================================
  // LOGIC WORKSPACE QUAN HỆ HỌC PHẦN (RELATIONS)
  // =========================================================================

  // 1. Cập nhật KPIs cho Relations workspace
  function updateRelationsKPIs() {
    if (!$('[data-relations-workspace]')) return;
    const totalCourses = state.courses.length;
    const prereqEdges = state.relations.filter(r => r.type === 'prerequisite');
    const coreqEdges = state.relations.filter(r => r.type === 'corequisite');

    const elTotal = $('[data-stat="rel-total-courses"]');
    const elPrereqs = $('[data-stat="rel-total-prereqs"]');
    const elCoreqs = $('[data-stat="rel-total-coreqs"]');
    const elPill = $('[data-stat="rel-courses-count-pill"]');

    if (elTotal) elTotal.textContent = totalCourses || '--';
    if (elPrereqs) elPrereqs.textContent = prereqEdges.length;
    if (elCoreqs) elCoreqs.textContent = coreqEdges.length;
    if (elPill) elPill.textContent = `${totalCourses} học phần`;

    // Tính toán số lượng cho từng filter pill
    const prereqCourseCodes = new Set(prereqEdges.map(r => r.course_code));
    const coreqCourseCodes = new Set(coreqEdges.map(r => r.course_code));

    let hasPrereqCount = 0;
    let hasCoreqCount = 0;
    let independentCount = 0;

    state.courses.forEach(c => {
      const hp = prereqCourseCodes.has(c.code);
      const hc = coreqCourseCodes.has(c.code);
      if (hp) hasPrereqCount++;
      if (hc) hasCoreqCount++;
      if (!hp && !hc) independentCount++;
    });

    const cAll = $('[data-rel-count="all"]');
    const cPre = $('[data-rel-count="has_prereq"]');
    const cCo = $('[data-rel-count="has_coreq"]');
    const cInd = $('[data-rel-count="independent"]');

    if (cAll) cAll.textContent = totalCourses;
    if (cPre) cPre.textContent = hasPrereqCount;
    if (cCo) cCo.textContent = hasCoreqCount;
    if (cInd) cInd.textContent = independentCount;
  }

  // 2. Render danh sách học phần ở sidebar bên trái
  function renderCourseResults() {
    const root = $('[data-course-results]');
    if (!root) return;

    if (!state.coursesLoaded && !state.courses.length) {
      root.innerHTML = '<div class="to-loading">Đang nạp danh sách học phần...</div>';
      return;
    }

    const query = (state.courseSearchQuery || '').trim().toLowerCase();

    if (!query) {
      root.style.display = 'none';
      root.innerHTML = '';
      return;
    }
    root.style.display = 'grid';

    // Xây dựng chỉ mục quan hệ
    const prereqCounts = {};
    const coreqCounts = {};
    const unlockCounts = {};

    state.relations.forEach(r => {
      if (r.type === 'prerequisite') {
        prereqCounts[r.course_code] = (prereqCounts[r.course_code] || 0) + 1;
        unlockCounts[r.related_course_code] = (unlockCounts[r.related_course_code] || 0) + 1;
      } else if (r.type === 'corequisite') {
        coreqCounts[r.course_code] = (coreqCounts[r.course_code] || 0) + 1;
      }
    });

    // Lọc danh sách
    const filtered = state.courses.filter(course => {
      const code = course.code;
      const pCount = prereqCounts[code] || 0;
      const cCount = coreqCounts[code] || 0;

      const str = `${course.code} ${course.name}`.toLowerCase();
      if (!str.includes(query)) return false;

      return true;
    });

    // Toggle nút xóa tìm kiếm
    const clearBtn = $('[data-action="clear-course-search"]');
    if (clearBtn) {
      clearBtn.style.display = query ? 'grid' : 'none';
    }

    if (!filtered.length) {
      root.innerHTML = `
        <div class="to-loading" style="padding:32px 16px;text-align:center;">
          <p style="color:#0f172a;font-weight:700;margin-bottom:4px;">Không tìm thấy học phần</p>
          <span style="font-size:0.75rem;color:#64748b;">Thử thay đổi từ khóa hoặc bộ lọc.</span>
        </div>`;
      return;
    }

    root.innerHTML = filtered.map(course => {
      const isActive = state.selectedCourse?.code === course.code;
      const pCount = prereqCounts[course.code] || 0;
      const cCount = coreqCounts[course.code] || 0;
      const uCount = unlockCounts[course.code] || 0;

      return `
        <button type="button" class="to-course-item ${isActive ? 'is-active' : ''}" data-select-course="${esc(course.code)}">
          <div class="to-course-item__top">
            <span class="to-course-item__code">${esc(course.code)}</span>
            <span class="to-course-item__credits">${Number(course.credits || 0)} TC</span>
          </div>
          <div class="to-course-item__name" title="${esc(course.name)}">${esc(course.name || 'Chưa đặt tên')}</div>
          <div class="to-course-item__badges">
            ${pCount > 0 ? `<span class="to-micro-badge to-micro-badge--prereq" title="${pCount} môn tiên quyết"><i data-lucide="arrow-left"></i> ${pCount} TQ</span>` : ''}
            ${uCount > 0 ? `<span class="to-micro-badge to-micro-badge--unlock" title="Mở khóa cho ${uCount} môn sau"><i data-lucide="arrow-right"></i> Mở ${uCount} môn</span>` : ''}
            ${cCount > 0 ? `<span class="to-micro-badge to-micro-badge--coreq" title="Có môn song hành"><i data-lucide="repeat"></i> Song hành</span>` : ''}
          </div>
        </button>
      `;
    }).join('');

    refreshIcons();
  }

  // 3. Render các chips Tiên quyết (Prerequisites)
  function renderPrereqChips() {
    const container = $('[data-prereq-chips]');
    if (!container) return;

    if (!state.editingPrereqs.length) {
      container.innerHTML = '<span class="to-tag-chips-empty">Chưa có môn tiên quyết nào (Học phần cơ sở / độc lập).</span>';
      return;
    }

    container.innerHTML = state.editingPrereqs.map(code => {
      const name = getCourseName(code);
      return `
        <span class="to-tag-chip">
          <strong>${esc(code)}</strong>
          ${name ? `<span style="font-weight:500;opacity:0.85;">${esc(name)}</span>` : ''}
          <button type="button" class="to-tag-chip__remove-btn" data-remove-prereq="${esc(code)}" title="Xóa ${esc(code)} khỏi danh sách tiên quyết">
            <i data-lucide="x"></i>
          </button>
        </span>
      `;
    }).join('');

    refreshIcons();
  }

  // 4. Render các chips Song hành (Corequisites)
  function renderCoreqChips() {
    const container = $('[data-coreq-chips]');
    if (!container) return;

    if (!state.editingCoreqs.length) {
      container.innerHTML = '<span class="to-tag-chips-empty">Không có học phần song hành nào.</span>';
      return;
    }

    container.innerHTML = state.editingCoreqs.map(code => {
      const name = getCourseName(code);
      return `
        <span class="to-tag-chip">
          <strong>${esc(code)}</strong>
          ${name ? `<span style="font-weight:500;opacity:0.85;">${esc(name)}</span>` : ''}
          <button type="button" class="to-tag-chip__remove-btn" data-remove-coreq="${esc(code)}" title="Xóa ${esc(code)} khỏi danh sách song hành">
            <i data-lucide="x"></i>
          </button>
        </span>
      `;
    }).join('');

    refreshIcons();
  }

  // 5. Cập nhật các select box để thêm nhanh tiên quyết/song hành
  function updateQuickAddDropdowns() {
    const pSelect = $('[data-add-prereq-select]');
    const cSelect = $('[data-add-coreq-select]');
    const pOptions = $('[data-add-prereq-options]');
    const cOptions = $('[data-add-coreq-options]');
    if (!state.selectedCourse || !state.courses.length) return;

    const curCode = state.selectedCourse.code;
    const availablePrereqs = state.courses.filter(c => c.code !== curCode && !state.editingPrereqs.includes(c.code));
    const availableCoreqs = state.courses.filter(c => c.code !== curCode && !state.editingCoreqs.includes(c.code));

    if (pSelect && pOptions) {
      pSelect.value = '';
      pOptions.innerHTML = availablePrereqs.map(c =>
        `<option value="${esc(c.code)}" label="${esc(c.name)} (${c.credits} TC)"></option>`
      ).join('');
    }

    if (cSelect && cOptions) {
      cSelect.value = '';
      cOptions.innerHTML = availableCoreqs.map(c =>
        `<option value="${esc(c.code)}" label="${esc(c.name)} (${c.credits} TC)"></option>`
      ).join('');
    }
  }

  // 6. Render sơ đồ luồng điều kiện học tập (Visual Dependency Pipeline)
  function renderDependencyFlow() {
    const container = $('[data-dependency-flow-container]');
    if (!container || !state.selectedCourse) return;

    const course = state.selectedCourse;
    const prereqs = state.editingPrereqs;
    const requiredBy = course.required_by || [];
    const chain = course.prerequisite_chain || [];

    let prereqHtml = '';
    if (prereqs.length > 0) {
      prereqHtml = `
        <div class="to-pipeline-stage">
          <span class="to-pipeline-stage__label"><i data-lucide="arrow-left-circle" style="color:#2563eb;"></i> Cần học trước (${prereqs.length})</span>
          <div class="to-pipeline-stage__nodes">
            ${prereqs.map(p => `
              <div class="to-flow-node to-flow-node--prereq">
                <span class="to-flow-node__code">${esc(p)}</span>
                <span style="font-size:0.72rem;color:#475569;">${esc(getCourseName(p))}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else {
      prereqHtml = `
        <div class="to-pipeline-stage">
          <span class="to-pipeline-stage__label"><i data-lucide="sparkles" style="color:#10b981;"></i> Điều kiện ban đầu</span>
          <div class="to-independent-notice">
            <i data-lucide="check-circle-2"></i>
            <div>
              <strong>Học phần cơ sở / độc lập</strong>
              <div style="font-size:0.75rem;margin-top:2px;">Sinh viên có thể đăng ký ngay từ kỳ 1 mà không phụ thuộc môn trước.</div>
            </div>
          </div>
        </div>
      `;
    }

    const currentHtml = `
      <div class="to-pipeline-stage">
        <span class="to-pipeline-stage__label"><i data-lucide="crosshair" style="color:#0f172a;"></i> Học phần đang chọn</span>
        <div class="to-flow-node to-flow-node--current">
          <div>
            <div class="to-flow-node__code">${esc(course.code)}</div>
            <div style="font-size:0.75rem;opacity:0.9;">${esc(course.name)}</div>
          </div>
          <span style="background:rgba(255,255,255,0.2);padding:2px 8px;border-radius:6px;font-size:0.72rem;">${Number(course.credits || 0)} TC</span>
        </div>
      </div>
    `;

    let unlockHtml = '';
    if (requiredBy.length > 0) {
      unlockHtml = `
        <div class="to-pipeline-stage">
          <span class="to-pipeline-stage__label"><i data-lucide="arrow-right-circle" style="color:#059669;"></i> Mở khóa các môn (${requiredBy.length})</span>
          <div class="to-pipeline-stage__nodes">
            ${requiredBy.map(u => `
              <button type="button" class="to-flow-node to-flow-node--unlock" data-jump-to="${esc(u)}" style="cursor:pointer;" title="Nhấp để xem môn ${esc(u)}">
                <span class="to-flow-node__code">${esc(u)}</span>
                <span style="font-size:0.72rem;color:#065f46;">${esc(getCourseName(u))}</span>
                <i data-lucide="arrow-up-right" style="width:12px;height:12px;margin-left:auto;"></i>
              </button>
            `).join('')}
          </div>
        </div>
      `;
    } else {
      unlockHtml = `
        <div class="to-pipeline-stage">
          <span class="to-pipeline-stage__label"><i data-lucide="flag" style="color:#64748b;"></i> Điểm đến của chuỗi</span>
          <div class="to-independent-notice" style="border-color:#e2e8f0;">
            <i data-lucide="info" style="color:#64748b;"></i>
            <div>
              <strong>Học phần chuyên đề / cuối chuỗi</strong>
              <div style="font-size:0.75rem;margin-top:2px;">Chưa làm điều kiện tiên quyết cho môn học nào tiếp theo.</div>
            </div>
          </div>
        </div>
      `;
    }

    let chainHtml = '';
    if (chain.length > 0) {
      chainHtml = `
        <div class="to-chain-list-wrap">
          <h5><i data-lucide="network" style="width:13px;height:13px;display:inline-block;vertical-align:-1px;"></i> Các nhánh quan hệ truyền tiếp (Transitive Chains):</h5>
          <div class="to-chain-steps">
            ${chain.map(edge => `
              <div class="to-chain-step-row">
                <button type="button" class="to-jump-chip" data-jump-to="${esc(edge.from)}" style="padding:2px 8px;">${esc(edge.from)}</button>
                <i data-lucide="arrow-right"></i>
                <button type="button" class="to-jump-chip" data-jump-to="${esc(edge.to)}" style="padding:2px 8px;">${esc(edge.to)}</button>
                <span style="color:#64748b;font-size:0.75rem;margin-left:auto;">
                  ${esc(getCourseName(edge.from))} ➔ ${esc(getCourseName(edge.to))}
                </span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="to-pipeline-container">
        ${prereqHtml}
        <div class="to-pipeline-arrow"><i data-lucide="arrow-right"></i></div>
        ${currentHtml}
        <div class="to-pipeline-arrow"><i data-lucide="arrow-right"></i></div>
        ${unlockHtml}
      </div>
      ${chainHtml}
    `;

    refreshIcons();
  }

  // 7. Render chi tiết học phần được chọn ở màn hình chính
  function renderCourseDetail(course) {
    const root = $('[data-course-detail]');
    if (!root) return;

    state.selectedCourse = course;
    state.originalSelectedCourse = JSON.parse(JSON.stringify(course));
    state.editingPrereqs = [...(course.prerequisites || [])];
    state.editingCoreqs = [...(course.corequisites || [])];

    const requiredBy = course.required_by || [];
    const credits = Number(course.credits || 0);

    let unlocksContent = '';
    if (requiredBy.length > 0) {
      unlocksContent = `
        <section class="to-unlocks-compact">
          <h5><i data-lucide="unlock"></i> Học phần được mở khóa (${requiredBy.length})</h5>
          <div class="to-unlocks-compact__chips">
              ${requiredBy.map(code => {
                const name = getCourseName(code);
                return `
                  <button type="button" class="to-jump-chip" data-jump-to="${esc(code)}" title="Nhấp để chuyển sang xem ${esc(code)}">
                    <strong>${esc(code)}</strong>
                    ${name ? `<span>• ${esc(name)}</span>` : ''}
                  </button>
                `;
              }).join('')}
          </div>
        </section>
      `;
    } else {
      unlocksContent = `
        <section class="to-unlocks-compact">
          <h5><i data-lucide="info"></i> Học phần được mở khóa</h5>
          <span class="to-unlocks-none">Chưa có học phần tiếp theo.</span>
        </section>
      `;
    }

    root.innerHTML = `
      <!-- BANNER TIÊU ĐỀ HỌC PHẦN -->
      <div class="to-course-header-banner">
        <div class="to-course-header-banner__left">
          <div class="to-course-header-banner__tags">
            <span class="to-course-code-pill">
              <span>${esc(course.code)}</span>
              <button type="button" class="to-course-code-copy-btn" data-copy-course-code="${esc(course.code)}" title="Sao chép mã môn">
                <i data-lucide="copy"></i>
              </button>
            </span>
            <span class="to-course-credits-badge">
              <i data-lucide="award" style="width:13px;height:13px;"></i>
              <span data-course-credits-label>${credits} Tín chỉ</span>
            </span>
            <span class="to-micro-badge" style="background:#f1f5f9;color:#475569;font-size:0.74rem;padding:3px 8px;">
              Khoa Công nghệ Thông tin
            </span>
          </div>
          <h2>${esc(course.name || 'Chưa đặt tên')}</h2>
        </div>

        <div class="to-course-header-banner__right">
          <span class="to-ontology-pill">
            <span class="to-pulse-dot"></span>
            Ontology Node
          </span>
        </div>
      </div>

      <!-- UNLOCKS BANNER -->
      ${unlocksContent}

      <!-- FORM BIÊN TẬP HỌC PHẦN -->
      <form class="to-course-form" data-course-form>
        <!-- BASIC INFO (TÊN & TÍN CHỈ) -->
        <div class="to-course-info-grid">
          <div class="to-field-block">
            <label>Tên học phần chính thức</label>
            <div class="to-field-input-wrap">
              <input type="text" name="name" required value="${esc(course.name)}" placeholder="Nhập tên học phần..." autocomplete="off">
            </div>
          </div>

          <div class="to-field-block">
            <label>Số tín chỉ (TC)</label>
            <div class="to-field-input-wrap">
              <input type="number" name="credits" data-input-credits min="0" max="30" step="0.5" required value="${credits}">
            </div>
            <div class="to-credits-quick-pills">
              <button type="button" class="to-credit-pill-btn ${credits === 1 ? 'is-selected' : ''}" data-quick-credit="1">1 TC</button>
              <button type="button" class="to-credit-pill-btn ${credits === 2 ? 'is-selected' : ''}" data-quick-credit="2">2 TC</button>
              <button type="button" class="to-credit-pill-btn ${credits === 3 ? 'is-selected' : ''}" data-quick-credit="3">3 TC</button>
              <button type="button" class="to-credit-pill-btn ${credits === 4 ? 'is-selected' : ''}" data-quick-credit="4">4 TC</button>
            </div>
          </div>
        </div>

        <!-- RELATIONS EDITOR GRID (PREREQUISITES & COREQUISITES) -->
        <div class="to-relations-editor-grid">
          <!-- CARD 1: TIÊN QUYẾT -->
          <section class="to-relation-card">
            <div class="to-relation-card__head">
              <div class="to-relation-card__title-box">
                <div class="to-relation-card__icon">
                  <i data-lucide="shield-alert"></i>
                </div>
                <div>
                  <h4>Học phần Tiên quyết</h4>
                  <p>Phải hoàn thành và đạt trước khi đăng ký môn này.</p>
                </div>
              </div>
            </div>

            <div class="to-tag-chips-container" data-prereq-chips>
              <!-- Populated by renderPrereqChips() -->
            </div>

            <div class="to-relation-quick-add">
              <input class="to-relation-select" type="search" list="prereq-course-options"
                data-add-prereq-select placeholder="Nhập mã môn tiên quyết..." autocomplete="off">
              <datalist id="prereq-course-options" data-add-prereq-options></datalist>
              <button type="button" class="to-relation-add-btn" data-action="add-prereq">
                <i data-lucide="plus"></i> Thêm
              </button>
            </div>
          </section>

          <!-- CARD 2: SONG HÀNH -->
          <section class="to-relation-card to-relation-card--coreq">
            <div class="to-relation-card__head">
              <div class="to-relation-card__title-box">
                <div class="to-relation-card__icon">
                  <i data-lucide="repeat"></i>
                </div>
                <div>
                  <h4>Học phần Song hành</h4>
                  <p>Học cùng kỳ hoặc hoàn thành trước.</p>
                </div>
              </div>
              <span class="to-symmetric-badge" title="Tự động đồng bộ 2 chiều">
                <i data-lucide="arrow-left-right" style="width:11px;height:11px;"></i> Đối xứng
              </span>
            </div>

            <div class="to-tag-chips-container" data-coreq-chips>
              <!-- Populated by renderCoreqChips() -->
            </div>

            <div class="to-relation-quick-add">
              <input class="to-relation-select" type="search" list="coreq-course-options"
                data-add-coreq-select placeholder="Nhập mã môn song hành..." autocomplete="off">
              <datalist id="coreq-course-options" data-add-coreq-options></datalist>
              <button type="button" class="to-relation-add-btn" data-action="add-coreq">
                <i data-lucide="plus"></i> Thêm
              </button>
            </div>
          </section>
        </div>

        <!-- FOOTER ACTIONS BAR (CLEAN, WHITE & ELEVATED) -->
        <div class="to-course-detail__footer">
          <div class="to-save-hint">
            <i data-lucide="info"></i>
            <span>Thay đổi được ghi trực tiếp vào Ontology RDF và phiên bản hóa.</span>
          </div>

          <div class="to-footer-actions">
            <button type="button" class="to-btn-revert" data-action="revert-course">
              <i data-lucide="rotate-ccw"></i> Hoàn tác
            </button>
            <button type="submit" class="to-btn-save" data-btn-save-course>
              <i data-lucide="save"></i> Lưu vào ontology
            </button>
          </div>
        </div>
      </form>
    `;

    renderPrereqChips();
    renderCoreqChips();
    updateQuickAddDropdowns();
    renderDependencyFlow();
    refreshIcons();
  }

  // 8. Chọn học phần theo mã
  async function selectCourse(code) {
    try {
      state.selectedCourse = await request(`/courses/${encodeURIComponent(code)}`);
      renderCourseResults();
      renderCourseDetail(state.selectedCourse);
    } catch (err) {
      const local = state.courses.find(course => course.code === code);
      if (local) {
        state.selectedCourse = local;
        renderCourseResults();
        renderCourseDetail(local);
      } else {
        message(err.message, 'error');
      }
    }
  }

  // 9. Nạp danh sách môn học vào modal Thêm quan hệ
  function populateRelationModalCourses() {
    const sourceSelect = $('[data-relation-select="source"]');
    const targetSelect = $('[data-relation-select="target"]');
    if (!sourceSelect || !targetSelect || !state.courses.length) return;

    const options = '<option value="">-- Chọn môn học --</option>' +
      state.courses.map(c => `<option value="${esc(c.code)}">${esc(c.code)} — ${esc(c.name)} (${c.credits} TC)</option>`).join('');

    sourceSelect.innerHTML = options;
    targetSelect.innerHTML = options;
  }

  function updateCurriculumTargets() {
    const scope = $('[data-curriculum-scope]')?.value || 'common';
    const target = $('[data-curriculum-targets]');
    const wrap = $('[data-curriculum-target-wrap]');
    if (!target || !wrap) return;
    const items = scope.endsWith('major') ? (state.courseFormOptions.majors || []) : (state.courseFormOptions.specializations || []);
    target.innerHTML = items.map(item => `<option value="${esc(item)}">${esc(item)}</option>`).join('');
    target.required = scope !== 'common';
    wrap.hidden = scope === 'common';
  }

  function populateCourseForm() {
    const options = state.courses.map(c => `<option value="${esc(c.code)}">${esc(c.code)} — ${esc(c.name)}</option>`).join('');
    $$('[data-course-prerequisites], [data-course-corequisites]').forEach(select => { select.innerHTML = options; });
    updateCurriculumTargets();
  }

  // =========================================================================
  // LOGIC WORKSPACE PHÂN CÔNG CỐ VẤN (ASSIGNMENTS)
  // =========================================================================

  function updateKPIs() {
    const list = state.assignments;
    const totalClasses = list.length;
    let totalStudents = 0;
    let assignedCount = 0;

    list.forEach(c => {
      totalStudents += (c.student_count || 0);
      if (c.assignment && c.assignment.advisor_username) {
        assignedCount++;
      }
    });

    const unassignedCount = totalClasses - assignedCount;
    const pct = totalClasses > 0 ? Math.round((assignedCount / totalClasses) * 100) : 0;
    const activeAdvisors = state.advisors.length;
    const avgWorkload = activeAdvisors > 0 ? (assignedCount / activeAdvisors).toFixed(1) : '0';

    const elTotal = $('[data-stat="total-classes"]');
    const elStudents = $('[data-stat="total-students"]');
    const elAssigned = $('[data-stat="assigned-classes"]');
    const elUnassigned = $('[data-stat="unassigned-classes"]');
    const elAdvisors = $('[data-stat="active-advisors"]');
    const elWorkload = $('[data-stat="avg-workload"]');
    const elFill = $('[data-stat="progress-fill"]');
    const elPct = $('[data-stat="progress-pct"]');

    if (elTotal) elTotal.textContent = totalClasses;
    if (elStudents) elStudents.textContent = `${totalStudents.toLocaleString()} sinh viên`;
    if (elAssigned) elAssigned.textContent = `${assignedCount} / ${totalClasses}`;
    if (elUnassigned) elUnassigned.textContent = unassignedCount;
    if (elAdvisors) elAdvisors.textContent = activeAdvisors;
    if (elWorkload) elWorkload.textContent = avgWorkload;
    if (elFill) elFill.style.width = `${pct}%`;
    if (elPct) elPct.textContent = `${pct}%`;

    const elTotalPill = $('[data-stat="total-classes-pill"]');
    if (elTotalPill) elTotalPill.textContent = `${totalClasses} lớp`;

    // Cập nhật số đếm trên filter pills
    const countAll = $('[data-pill-count="all"]');
    const countUn = $('[data-pill-count="unassigned"]');
    const countAsg = $('[data-pill-count="assigned"]');
    if (countAll) countAll.textContent = totalClasses;
    if (countUn) countUn.textContent = unassignedCount;
    if (countAsg) countAsg.textContent = assignedCount;

    // Cập nhật danh sách Khóa học (Cohorts)
    updateCohortFilterOptions();
  }

  function updateCohortFilterOptions() {
    const select = $('[data-filter-cohort]');
    if (!select) return;

    const cohorts = new Set();
    state.assignments.forEach(c => {
      const match = c.academic_class.match(/^(\d{2})/);
      if (match) cohorts.add(match[1]);
    });

    const currentVal = select.value || 'all';
    const sorted = Array.from(cohorts).sort();

    select.innerHTML = '<option value="all">Tất cả các khóa</option>' +
      sorted.map(co => `<option value="${co}" ${currentVal === co ? 'selected' : ''}>Khóa K${co}</option>`).join('');
  }

  function renderAssignments() {
    const body = $('[data-rows="assignments"]');
    if (!body) return;

    const query = state.searchQuery.toLowerCase().trim();
    const status = state.filterStatus;
    const cohort = state.filterCohort;

    // Lọc dữ liệu
    const rows = state.assignments.filter(item => {
      const isAssigned = !!(item.assignment && item.assignment.advisor_username);

      // Lọc theo trạng thái phân công
      if (status === 'assigned' && !isAssigned) return false;
      if (status === 'unassigned' && isAssigned) return false;

      // Lọc theo khóa học
      if (cohort !== 'all') {
        const match = item.academic_class.match(/^(\d{2})/);
        if (!match || match[1] !== cohort) return false;
      }

      // Lọc theo từ khóa tìm kiếm
      if (query) {
        const cls = item.academic_class.toLowerCase();
        const advisorUser = (item.assignment?.advisor_username || '').toLowerCase();
        const advisorName = (item.assignment?.advisor_name || '').toLowerCase();
        const hasMatchingStudent = (item.students || []).some(s =>
          (s.name || '').toLowerCase().includes(query) || (s.student_id || '').toLowerCase().includes(query)
        );

        if (!cls.includes(query) && !advisorUser.includes(query) && !advisorName.includes(query) && !hasMatchingStudent) {
          return false;
        }
      }

      return true;
    });

    if (!rows.length) {
      body.innerHTML = `
        <tr>
          <td colspan="5">
            <div class="to-empty-state">
              <i data-lucide="search-x"></i>
              <h3>Không tìm thấy lớp phù hợp</h3>
              <p>Thử thay đổi từ khóa tìm kiếm hoặc bỏ bớt các bộ lọc đang chọn.</p>
            </div>
          </td>
        </tr>`;
      refreshIcons();
      updateBatchBar();
      return;
    }

    body.innerHTML = rows.map(item => {
      const isSelected = state.selectedClasses.has(item.academic_class);
      const isAssigned = !!(item.assignment && item.assignment.advisor_username);
      const cohortMatch = item.academic_class.match(/^(\d{2})/);
      const cohortNum = cohortMatch ? `K${cohortMatch[1]}` : 'LỚP';

      let advisorHtml = '';
      if (isAssigned) {
        const advName = item.assignment.advisor_name || item.assignment.advisor_username;
        const initials = getInitials(advName);
        const assignedDate = formatDate(item.assignment.assigned_at);

        advisorHtml = `
          <div class="to-advisor-cell">
            <div class="to-advisor-avatar">${esc(initials)}</div>
            <div class="to-advisor-info">
              <span class="to-advisor-name">${esc(advName)}</span>
              <span class="to-advisor-username">
                ${esc(item.assignment.advisor_username)}${assignedDate ? ` • ${assignedDate}` : ''}
              </span>
            </div>
          </div>
        `;
      } else {
        advisorHtml = `
          <span class="to-unassigned-badge">
            <span class="to-pulse-dot"></span>
            Chưa phân công
          </span>
        `;
      }

      const actionBtn = isAssigned
        ? `<button type="button" class="to-btn-edit-assign" data-class-detail="${esc(item.academic_class)}" title="Thay đổi cố vấn">
             <i data-lucide="user-cog"></i> Đổi cố vấn
           </button>`
        : `<button type="button" class="to-btn-assign-quick" data-class-detail="${esc(item.academic_class)}" title="Phân công cố vấn cho lớp này">
             <i data-lucide="user-plus"></i> Phân công
           </button>`;

      return `
        <tr class="${isSelected ? 'is-selected' : ''}" data-class-row="${esc(item.academic_class)}">
          <td>
            <div class="to-class-meta">
              <span class="to-cohort-badge">${esc(cohortNum)}</span>
              <div>
                <div class="to-class-name">${esc(item.academic_class)}</div>
                <div class="to-class-major">Công nghệ thông tin</div>
              </div>
            </div>
          </td>
          <td style="text-align:center;">
            <button type="button" class="to-student-pill to-student-pill--clickable" data-action="view-roster" data-class="${esc(item.academic_class)}" title="Bấm để xem danh sách ${item.student_count} sinh viên lớp ${esc(item.academic_class)}">
              <i data-lucide="users"></i>
              <span>${item.student_count} sinh viên</span>
              <i data-lucide="arrow-up-right" class="to-pill-arrow"></i>
            </button>
          </td>
          <td style="text-align:center;">
            ${advisorHtml}
          </td>
          <td style="text-align:center;">
            <div class="to-action-group">
              ${actionBtn}
              ${isAssigned ? `
                <button type="button" class="to-icon-button" data-revoke-advisor="${esc(item.assignment.advisor_username)}" data-academic-class="${esc(item.academic_class)}" title="Gỡ cố vấn" style="color:#ef4444;">
                  <i data-lucide="user-minus"></i>
                </button>
              ` : ''}
            </div>
          </td>
          <td style="width:56px;text-align:center;padding-right:24px;">
            <input type="checkbox" class="to-checkbox" data-select-class="${esc(item.academic_class)}" ${isSelected ? 'checked' : ''} aria-label="Chọn lớp ${esc(item.academic_class)}">
          </td>
        </tr>
      `;
    }).join('');

    // Checkbox All state
    const selectAllBox = $('[data-select-all-classes]');
    if (selectAllBox) {
      const allChecked = rows.length > 0 && rows.every(r => state.selectedClasses.has(r.academic_class));
      selectAllBox.checked = allChecked;
    }

    refreshIcons();
    updateBatchBar();
  }

  function updateBatchBar() {
    const bar = $('[data-batch-bar]');
    const countEl = $('[data-batch-count]');
    if (!bar) return;

    const count = state.selectedClasses.size;
    if (count > 0) {
      bar.classList.add('is-visible');
      if (countEl) countEl.textContent = count;
    } else {
      bar.classList.remove('is-visible');
    }
  }

  // Mở Modal Phân công Cố vấn cho Lớp (Chuyên biệt, không có tab)
  function openClassModal(academicClass) {
    const row = state.assignments.find(x => x.academic_class === academicClass);
    if (!row) return;

    state.currentClass = row;

    const dialog = $('[data-dialog="assignment"]');
    if (!dialog) return;

    // Header thông tin
    $('[data-modal-class-title]').textContent = `Lớp ${row.academic_class}`;
    $('[data-modal-student-count]').textContent = row.student_count;
    $('[data-input-class]').value = row.academic_class;

    const statusBadge = $('[data-modal-status-badge]');
    if (statusBadge) {
      if (row.assignment && row.assignment.advisor_username) {
        statusBadge.className = 'to-stat-card__badge to-stat-card__badge--emerald';
        statusBadge.innerHTML = '<i data-lucide="check-circle" style="width:12px;height:12px;display:inline-block;vertical-align:-1px;"></i> Đã phân công';
      } else {
        statusBadge.className = 'to-stat-card__badge to-stat-card__badge--amber';
        statusBadge.innerHTML = '<i data-lucide="alert-circle" style="width:12px;height:12px;display:inline-block;vertical-align:-1px;"></i> Chưa phân công';
      }
    }

    // Hiển thị Banner cố vấn hiện tại nếu có
    const banner = $('[data-current-advisor-banner]');
    if (row.assignment && row.assignment.advisor_username) {
      banner.style.display = 'flex';
      const advName = row.assignment.advisor_name || row.assignment.advisor_username;
      $('[data-current-advisor-name]').textContent = advName;
      $('[data-current-advisor-user]').textContent = `Mã cán bộ: ${row.assignment.advisor_username}${row.assignment.assigned_at ? ` • Phân công: ${formatDate(row.assignment.assigned_at)}` : ''}`;
      $('[data-current-advisor-avatar]').textContent = getInitials(advName);
    } else {
      banner.style.display = 'none';
    }

    // Render danh sách Thẻ chọn Cố vấn (Advisor Cards)
    renderAdvisorSelectionCards(row.assignment ? row.assignment.advisor_username : '');

    refreshIcons();
    dialog.showModal();
  }

  // Mở Modal Danh sách Sinh viên chuyên biệt
  function openRosterModal(academicClass) {
    const row = state.assignments.find(x => x.academic_class === academicClass);
    if (!row) return;

    state.currentRosterClass = row;
    state.rosterQuery = '';

    const dialog = $('[data-dialog="roster"]');
    if (!dialog) return;

    $('[data-roster-class-title]').textContent = `Danh sách sinh viên lớp ${row.academic_class}`;
    $('[data-roster-student-count]').textContent = row.student_count;

    const cohortMatch = row.academic_class.match(/^(\d{2})/);
    const cohortBadge = $('[data-roster-cohort-badge]');
    if (cohortBadge) {
      cohortBadge.textContent = cohortMatch ? `Khóa K${cohortMatch[1]}` : 'Lớp chính quy';
    }

    const filterInput = $('[data-roster-filter]');
    if (filterInput) filterInput.value = '';

    renderStudentRoster(row.students || []);

    refreshIcons();
    dialog.showModal();
  }

  function renderAdvisorSelectionCards(currentAdvisorUsername) {
    const container = $('[data-advisor-cards-list]');
    const select = $('[data-advisor-select]');
    if (!container) return;

    if (!state.advisors.length) {
      container.innerHTML = '<div class="to-empty-state"><p>Chưa có tài khoản Cố vấn học tập nào được kích hoạt.</p></div>';
      if (select) select.innerHTML = '';
      return;
    }

    // Populate hidden select
    if (select) {
      select.innerHTML = '<option value="">-- Chọn cố vấn --</option>' +
        state.advisors.map(a => `<option value="${esc(a.username)}" ${a.username === currentAdvisorUsername ? 'selected' : ''}>${esc(a.name)}</option>`).join('');
    }

    // Render interactive cards
    container.innerHTML = state.advisors.map(adv => {
      const isSelected = adv.username === currentAdvisorUsername;
      const initials = getInitials(adv.name);
      const count = adv.assigned_classes_count || 0;

      let workloadClass = 'to-workload-badge--low';
      let workloadText = `Phụ trách ${count} lớp`;
      if (count >= 4) {
        workloadClass = 'to-workload-badge--high';
        workloadText = `Tải cao (${count} lớp)`;
      } else if (count >= 2) {
        workloadClass = 'to-workload-badge--med';
        workloadText = `${count} lớp`;
      }

      return `
        <div class="to-advisor-card-option ${isSelected ? 'is-selected' : ''}" data-choose-advisor="${esc(adv.username)}">
          <div class="to-advisor-card-option__left">
            <div class="to-advisor-avatar to-advisor-avatar--emerald">${esc(initials)}</div>
            <div class="to-advisor-card-option__meta">
              <span class="to-advisor-card-option__name">${esc(adv.name)}</span>
              <span class="to-advisor-card-option__username">${esc(adv.username)}</span>
            </div>
          </div>
          <div class="to-advisor-card-option__right">
            <span class="to-workload-badge ${workloadClass}">${workloadText}</span>
            <div class="to-radio-custom"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderStudentRoster(students) {
    const tbody = $('[data-roster-rows]');
    if (!tbody) return;

    const q = (state.rosterQuery || '').toLowerCase().trim();
    const filtered = (students || []).filter(s => {
      if (!q) return true;
      return (s.name || '').toLowerCase().includes(q) || (s.student_id || '').toLowerCase().includes(q);
    });

    const summary = $('[data-roster-footer-summary]');
    if (summary) {
      summary.innerHTML = `Hiển thị <strong>${filtered.length}</strong> / ${students.length} sinh viên`;
    }

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="to-loading">Không tìm thấy sinh viên phù hợp.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map((s, idx) => `
      <tr>
        <td style="text-align:center;color:#64748b;font-weight:600;">${idx + 1}</td>
        <td><span class="to-student-id-badge">${esc(s.student_id)}</span></td>
        <td><strong style="color:#0f172a;font-size:0.87rem;">${esc(s.name)}</strong></td>
        <td><span style="color:#475569;">${esc(s.major || 'Công nghệ thông tin')}</span></td>
        <td style="text-align:center;"><span class="to-semester-badge">Kỳ ${esc(s.semester || 1)}</span></td>
      </tr>
    `).join('');
  }

  // Mở Modal Phân công hàng loạt
  function openBatchModal() {
    if (state.selectedClasses.size === 0) {
      message('Vui lòng chọn ít nhất 1 lớp để phân công hàng loạt.', 'error');
      return;
    }

    const dialog = $('[data-dialog="batch-assignment"]');
    if (!dialog) return;

    $('[data-batch-modal-count]').textContent = state.selectedClasses.size;

    // Tags các lớp được chọn
    const tagsContainer = $('[data-batch-class-tags]');
    if (tagsContainer) {
      tagsContainer.innerHTML = Array.from(state.selectedClasses).map(cls => `
        <span class="to-cohort-badge" style="width:auto;padding:2px 8px;font-size:0.75rem;">${esc(cls)}</span>
      `).join('');
    }

    // Render danh sách cố vấn
    const container = $('[data-batch-advisor-cards-list]');
    const select = $('[data-batch-advisor-select]');
    if (container && select) {
      select.innerHTML = '<option value="">-- Chọn cố vấn --</option>' +
        state.advisors.map(a => `<option value="${esc(a.username)}">${esc(a.name)}</option>`).join('');

      container.innerHTML = state.advisors.map(adv => {
        const initials = getInitials(adv.name);
        const count = adv.assigned_classes_count || 0;
        return `
          <div class="to-advisor-card-option" data-batch-choose-advisor="${esc(adv.username)}">
            <div class="to-advisor-card-option__left">
              <div class="to-advisor-avatar to-advisor-avatar--emerald">${esc(initials)}</div>
              <div class="to-advisor-card-option__meta">
                <span class="to-advisor-card-option__name">${esc(adv.name)}</span>
                <span class="to-advisor-card-option__username">${esc(adv.username)}</span>
              </div>
            </div>
            <div class="to-advisor-card-option__right">
              <span class="to-workload-badge to-workload-badge--low">Phụ trách: ${count} lớp</span>
              <div class="to-radio-custom"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    refreshIcons();
    dialog.showModal();
  }

  // =========================================================================
  // LOGIC CHUNG & KHỞI TẠO TẤT CẢ WORKSPACES
  // =========================================================================

  function render(kind) {
    if (kind === 'assignments') {
      updateKPIs();
      renderAssignments();
      return;
    }

    const body = $(`[data-rows="${kind}"]`);
    if (!body) return;
    const filter = ($(`[data-filter="${kind}"]`)?.value || '').toLowerCase();
    const rows = state[kind].filter(x => Object.values(x).join(' ').toLowerCase().includes(filter));
    const count = $(`[data-count="${kind}"]`);
    if (count) count.textContent = `${rows.length} bản ghi`;

    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4" class="to-loading">Không có dữ liệu phù hợp.</td></tr>';
      return;
    }

    if (kind === 'relations') {
      body.innerHTML = rows.map(x => `
        <tr>
          <td><span class="to-badge to-badge--blue">${x.type === 'prerequisite' ? 'Tiên quyết' : 'Song hành'}</span></td>
          <td><strong>${esc(x.course_code)}</strong></td>
          <td>${esc(x.related_course_code)}</td>
          <td><button class="to-action" data-remove-relation data-type="${x.type}" data-course="${esc(x.course_code)}" data-related="${esc(x.related_course_code)}">Xóa</button></td>
        </tr>
      `).join('');
    }

    if (kind === 'programs') {
      body.innerHTML = rows.map(x => `
        <tr>
          <td><strong>${esc(x.program_id)}</strong></td>
          <td>${esc(x.name)}</td>
          <td><span class="to-badge ${x.archived ? 'to-badge--gray' : 'to-badge--green'}">${x.archived ? 'Đã lưu trữ' : 'Đang hoạt động'}</span></td>
          <td>${x.archived ? '' : `<button class="to-action to-edit" data-edit-program="${esc(x.program_id)}" data-program-name="${esc(x.name)}">Cập nhật</button><button class="to-action" data-archive-program="${esc(x.program_id)}">Lưu trữ</button>`}</td>
        </tr>
      `).join('');
    }

    refreshIcons();
  }

  async function load(kind, path) {
    const body = $(`[data-rows="${kind}"]`);
    if (!body) return;
    try {
      state[kind] = await request(path);
      render(kind);
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="to-loading">${esc(e.message)}</td></tr>`;
    }
  }

  async function loadAll() {
    try {
      // Tải danh sách cố vấn trước để có thông tin workload và tên
      const advisorsPromise = request('/advisors')
        .then(res => { state.advisors = res; })
        .catch(() => { state.advisors = []; });

      const coursesPromise = (state.coursesLoaded ? Promise.resolve(state.courses) : request('/courses'))
        .then(rows => {
          state.courses = rows;
          state.coursesLoaded = true;
        })
        .catch(() => {
          state.courses = [];
        });

      await Promise.all([
        load('relations', '/relations'),
        load('programs', '/programs'),
        advisorsPromise,
        coursesPromise
      ]);

      // Cập nhật giao diện nếu đang ở workspace relations
      if ($('[data-relations-workspace]')) {
        updateRelationsKPIs();
        renderCourseResults();
        populateRelationModalCourses();

      }

      // Sau khi có advisors thì nạp academic-classes
      await load('assignments', '/academic-classes');
    } catch (err) {
      console.error('Lỗi khi tải dữ liệu ban đầu:', err);
    }
  }

  // =========================================================================
  // GẮN SỰ KIỆN TƯƠNG TÁC
  // =========================================================================

  document.addEventListener('DOMContentLoaded', () => {
    // Đọc danh mục học phần nhúng sẵn nếu có
    const courseCatalog = $('[data-course-catalog]');
    const courseFormOptions = $('[data-course-form-options]');
    if (courseFormOptions) {
      try { state.courseFormOptions = JSON.parse(courseFormOptions.textContent || '{}'); }
      catch (err) { console.error('Không thể đọc tùy chọn tạo học phần:', err); }
    }
    if (courseCatalog) {
      try {
        state.courses = JSON.parse(courseCatalog.textContent || '[]');
        state.coursesLoaded = true;
        updateRelationsKPIs();
        renderCourseResults();

      } catch (err) {
        console.error('Không thể đọc danh mục học phần nhúng sẵn:', err);
      }
    }

    // Tìm kiếm học phần (Relations Workspace)
    $('[data-course-search]')?.addEventListener('input', (e) => {
      state.courseSearchQuery = e.target.value;
      renderCourseResults();
    });

    $('[data-curriculum-scope]')?.addEventListener('change', updateCurriculumTargets);

    // Xóa tìm kiếm
    $('[data-action="clear-course-search"]')?.addEventListener('click', () => {
      state.courseSearchQuery = '';
      const input = $('[data-course-search]');
      if (input) input.value = '';
      renderCourseResults();
    });

    // Nút làm mới quan hệ học phần
    $('[data-action="refresh-relations"]')?.addEventListener('click', async () => {
      const btn = $('[data-action="refresh-relations"]');
      if (btn) btn.disabled = true;
      try {
        await loadAll();
        message('Đã làm mới dữ liệu học phần.');
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    // Chọn học phần từ sidebar kết quả
    document.addEventListener('click', async (e) => {
      const button = e.target.closest('[data-select-course]');
      if (!button) return;
      try { await selectCourse(button.dataset.selectCourse); }
      catch (err) { message(err.message, 'error'); }
    });

    // Chuyển sang môn học khác từ chip hoặc đồ thị
    document.addEventListener('click', async (e) => {
      const jumpBtn = e.target.closest('[data-jump-to]');
      if (!jumpBtn) return;
      const code = jumpBtn.dataset.jumpTo;
      if (code) {
        await selectCourse(code);
      }
    });

    // Sao chép mã môn học
    document.addEventListener('click', (e) => {
      const copyBtn = e.target.closest('[data-copy-course-code]');
      if (!copyBtn) return;
      const code = copyBtn.dataset.copyCourseCode;
      if (navigator.clipboard && code) {
        navigator.clipboard.writeText(code).then(() => {
          message(`Đã sao chép mã học phần: ${code}`);
        });
      }
    });

    // Chọn nhanh số tín chỉ từ pill
    document.addEventListener('click', (e) => {
      const pillBtn = e.target.closest('[data-quick-credit]');
      if (!pillBtn) return;
      const credits = Number(pillBtn.dataset.quickCredit);
      const input = $('[data-input-credits]');
      if (input) {
        input.value = credits;
        $$('[data-quick-credit]').forEach(b => b.classList.remove('is-selected'));
        pillBtn.classList.add('is-selected');
        const label = $('[data-course-credits-label]');
        if (label) label.textContent = `${credits} Tín chỉ`;
      }
    });

    // Thêm môn tiên quyết
    document.addEventListener('click', (e) => {
      const addBtn = e.target.closest('[data-action="add-prereq"]');
      if (!addBtn) return;
      const select = $('[data-add-prereq-select]');
      if (!select || !select.value) return;

      const code = select.value.trim().toUpperCase();
      if (!state.courses.some(course => course.code === code)) {
        message('Vui lòng chọn mã học phần hợp lệ từ danh sách gợi ý.', 'error');
        return;
      }
      if (!state.editingPrereqs.includes(code)) {
        confirmRelationChange('Thêm học phần tiên quyết', `Thêm ${code} vào danh sách học phần tiên quyết?`, 'Xác nhận thêm', () => {
          state.editingPrereqs.push(code);
          renderPrereqChips();
          updateQuickAddDropdowns();
          renderDependencyFlow();
        }, { isRemoval: false, code, courseName: getCourseName(code) });
      }
    });

    // Xóa môn tiên quyết
    document.addEventListener('click', (e) => {
      const removeBtn = e.target.closest('[data-remove-prereq]');
      if (!removeBtn) return;
      const code = removeBtn.dataset.removePrereq;
      confirmRelationChange('Xóa học phần tiên quyết', `Xóa ${code} khỏi danh sách học phần tiên quyết?`, 'Xác nhận xóa', () => {
        state.editingPrereqs = state.editingPrereqs.filter(c => c !== code);
        renderPrereqChips();
        updateQuickAddDropdowns();
        renderDependencyFlow();
      }, { isRemoval: true, code, courseName: getCourseName(code) });
    });

    // Thêm môn song hành
    document.addEventListener('click', (e) => {
      const addBtn = e.target.closest('[data-action="add-coreq"]');
      if (!addBtn) return;
      const select = $('[data-add-coreq-select]');
      if (!select || !select.value) return;

      const code = select.value.trim().toUpperCase();
      if (!state.courses.some(course => course.code === code)) {
        message('Vui lòng chọn mã học phần hợp lệ từ danh sách gợi ý.', 'error');
        return;
      }
      if (!state.editingCoreqs.includes(code)) {
        confirmRelationChange('Thêm học phần song hành', `Thêm ${code} vào danh sách học phần song hành?`, 'Xác nhận thêm', () => {
          state.editingCoreqs.push(code);
          renderCoreqChips();
          updateQuickAddDropdowns();
          renderDependencyFlow();
        }, { isRemoval: false, code, courseName: getCourseName(code) });
      }
    });

    // Xóa môn song hành
    document.addEventListener('click', (e) => {
      const removeBtn = e.target.closest('[data-remove-coreq]');
      if (!removeBtn) return;
      const code = removeBtn.dataset.removeCoreq;
      confirmRelationChange('Xóa học phần song hành', `Xóa ${code} khỏi danh sách học phần song hành?`, 'Xác nhận xóa', () => {
        state.editingCoreqs = state.editingCoreqs.filter(c => c !== code);
        renderCoreqChips();
        updateQuickAddDropdowns();
        renderDependencyFlow();
      }, { isRemoval: true, code, courseName: getCourseName(code) });
    });

    // Nút Hoàn tác (Revert course edits)
    document.addEventListener('click', (e) => {
      const revertBtn = e.target.closest('[data-action="revert-course"]');
      if (!revertBtn || !state.originalSelectedCourse) return;
      renderCourseDetail(state.originalSelectedCourse);
      message('Đã hoàn tác các thay đổi chưa lưu.');
    });

    // Submit form chi tiết học phần (Save to Ontology)
    document.addEventListener('submit', async (e) => {
      const form = e.target.closest('[data-form="course"]');
      if (!form) return;
      e.preventDefault();

      const submit = form.querySelector('[type="submit"]');
      const courseCode = form.course_code.value.trim().toUpperCase();
      try {
        if (submit) submit.disabled = true;
        const data = await request('/courses', {
          method: 'POST',
          body: JSON.stringify({
            course_code: courseCode,
            name: form.name.value.trim(),
            credits: Number(form.credits.value)
          })
        });
        state.courses.push(data);
        state.courses.sort((a, b) => a.code.localeCompare(b.code));
        updateRelationsKPIs();
        renderCourseResults();
        populateRelationModalCourses();
        form.closest('dialog')?.close();
        await selectCourse(data.code);
        message(`Đã thêm học phần ${data.code} vào ontology.`);
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (submit) submit.disabled = false;
      }
    });

    document.addEventListener('submit', async (e) => {
      const form = e.target.closest('[data-course-form]');
      if (!form || !state.selectedCourse) return;
      e.preventDefault();

      const submit = form.querySelector('[type="submit"]');
      const courseCode = state.selectedCourse.code;
      const name = form.name.value.trim();
      const credits = parseFloat(form.credits.value) || 0;

      try {
        if (submit) submit.disabled = true;
        const data = await request(`/courses/${encodeURIComponent(courseCode)}`, {
          method: 'PUT',
          body: JSON.stringify({
            name,
            credits,
            prerequisites: state.editingPrereqs,
            corequisites: state.editingCoreqs
          })
        });

        state.selectedCourse = data;
        state.originalSelectedCourse = JSON.parse(JSON.stringify(data));

        // Cập nhật lại trong mảng courses
        const idx = state.courses.findIndex(c => c.code === courseCode);
        if (idx !== -1) {
          state.courses[idx] = { ...state.courses[idx], name, credits };
        }

        // Tải lại quan hệ toàn hệ thống để cập nhật đồ thị
        await load('relations', '/relations');
        updateRelationsKPIs();
        renderCourseResults();
        renderCourseDetail(data);

        message(`Đã lưu học phần ${courseCode} và các ràng buộc vào ontology.`);
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (submit) submit.disabled = false;
      }
    });

    // 1. Mở modal thêm quan hệ / CTĐT
    $$('[data-dialog-open]').forEach(b => b.addEventListener('click', () => {
      const dialog = $(`[data-dialog="${b.dataset.dialogOpen}"]`);
      if (b.dataset.dialogOpen === 'program') {
        const f = $('[data-form="program"]');
        f.reset();
        f.mode.value = 'create';
        f.program_id.readOnly = false;
        $('[data-program-dialog-title]').textContent = 'Tạo chương trình đào tạo';
        $('[data-program-submit]').textContent = 'Tạo chương trình';
      }
      if (b.dataset.dialogOpen === 'relation') {
        populateRelationModalCourses();
      }
      if (b.dataset.dialogOpen === 'course') {
        const form = $('[data-form="course"]');
        form?.reset();
        populateCourseForm();
      }
      if (dialog) dialog.showModal();
    }));

    // 2. Đóng modals khi click nút data-modal-close
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-modal-close]');
      if (btn) {
        const dialog = btn.closest('dialog');
        if (dialog) dialog.close();
      }
    });

    document.addEventListener('click', (e) => {
      const cancel = e.target.closest('[data-confirm-relation-cancel]');
      if (cancel) {
        state.pendingRelationAction = null;
        $('[data-confirm-relation-dialog]')?.close();
        return;
      }
      const accept = e.target.closest('[data-confirm-relation-submit]');
      if (!accept || !state.pendingRelationAction) return;
      const action = state.pendingRelationAction;
      state.pendingRelationAction = null;
      $('[data-confirm-relation-dialog]')?.close();
      action();
    });

    // Backdrop click đóng modal & Cancel cleanup
    const confirmDialog = $('[data-confirm-relation-dialog]');
    if (confirmDialog) {
      confirmDialog.addEventListener('click', (e) => {
        if (e.target === confirmDialog) {
          state.pendingRelationAction = null;
          confirmDialog.close();
        }
      });
      confirmDialog.addEventListener('cancel', () => {
        state.pendingRelationAction = null;
      });
    }

    // Generic backdrop click for all modals
    document.querySelectorAll('dialog.to-modal-dialog, dialog.to-dialog').forEach(d => {
      d.addEventListener('click', (e) => {
        if (e.target === d) d.close();
      });
    });

    // 3. Lọc tìm kiếm sinh viên trong Roster Modal
    $('[data-roster-filter]')?.addEventListener('input', (e) => {
      state.rosterQuery = e.target.value;
      if (state.currentRosterClass) {
        renderStudentRoster(state.currentRosterClass.students || []);
      }
    });

    // 5. Chọn thẻ cố vấn trong Modal (Single Assignment)
    document.addEventListener('click', (e) => {
      const card = e.target.closest('[data-choose-advisor]');
      if (card) {
        const username = card.dataset.chooseAdvisor;
        $$('[data-choose-advisor]').forEach(c => c.classList.remove('is-selected'));
        card.classList.add('is-selected');
        const select = $('[data-advisor-select]');
        if (select) select.value = username;
      }
    });

    // 6. Chọn thẻ cố vấn trong Modal Phân công hàng loạt (Batch Assignment)
    document.addEventListener('click', (e) => {
      const card = e.target.closest('[data-batch-choose-advisor]');
      if (card) {
        const username = card.dataset.batchChooseAdvisor;
        $$('[data-batch-choose-advisor]').forEach(c => c.classList.remove('is-selected'));
        card.classList.add('is-selected');
        const select = $('[data-batch-advisor-select]');
        if (select) select.value = username;
      }
    });

    // 7. Lọc theo trạng thái phân công (Filter Pills)
    $$('[data-filter-status]').forEach(pill => {
      pill.addEventListener('click', () => {
        $$('[data-filter-status]').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        state.filterStatus = pill.dataset.filterStatus;
        renderAssignments();
      });
    });

    // 8. Lọc theo Khóa học (Cohort select)
    $('[data-filter-cohort]')?.addEventListener('change', (e) => {
      state.filterCohort = e.target.value;
      renderAssignments();
    });

    // 9. Ô tìm kiếm chính (Live search)
    $('[data-filter="assignments"]')?.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      renderAssignments();
    });

    // Lọc cho programs
    $$('[data-filter]:not([data-filter="assignments"])').forEach(i => {
      i.addEventListener('input', () => render(i.dataset.filter));
    });

    // 10. Checkbox Chọn tất cả (Select All)
    $('[data-select-all-classes]')?.addEventListener('change', (e) => {
      const isChecked = e.target.checked;
      state.selectedClasses.clear();
      if (isChecked) {
        state.assignments.forEach(c => state.selectedClasses.add(c.academic_class));
      }
      renderAssignments();
    });

    // 11. Checkbox Chọn từng lớp
    document.addEventListener('change', (e) => {
      const chk = e.target.closest('[data-select-class]');
      if (chk) {
        const cls = chk.dataset.selectClass;
        if (chk.checked) {
          state.selectedClasses.add(cls);
        } else {
          state.selectedClasses.delete(cls);
        }
        renderAssignments();
      }
    });

    // 12. Bỏ chọn hàng loạt
    $('[data-action="clear-batch-selection"]')?.addEventListener('click', () => {
      state.selectedClasses.clear();
      renderAssignments();
    });

    // 13. Mở modal phân công hàng loạt
    $('[data-action="open-batch-assign"]')?.addEventListener('click', () => {
      openBatchModal();
    });

    // 14. Nút Làm mới (Refresh Assignments)
    $('[data-action="refresh-assignments"]')?.addEventListener('click', async () => {
      const btn = $('[data-action="refresh-assignments"]');
      if (btn) btn.disabled = true;
      try {
        await loadAll();
        message('Đã làm mới dữ liệu.');
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    // 15. Submit Form Phân Công Đơn Lẻ (Single Assignment Form)
    $('[data-form="assignment"]')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const academicClass = form.academic_class.value;
      const advisorUsername = form.advisor_username.value;

      if (!advisorUsername) {
        message('Vui lòng chọn một cố vấn học tập.', 'error');
        return;
      }

      const submitBtn = $('[data-btn-save-assignment]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        await request('/advisor-assignments', {
          method: 'POST',
          body: JSON.stringify({ advisor_username: advisorUsername, academic_class: academicClass })
        });
        form.closest('dialog')?.close();
        await loadAll();
        message(`Đã phân công ${advisorUsername} cho lớp ${academicClass}.`);
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    // 16. Submit Form Phân Công Hàng Loạt (Batch Assignment Form)
    $('[data-form="batch-assignment"]')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const advisorUsername = form.batch_advisor_username.value;

      if (!advisorUsername) {
        message('Vui lòng chọn một cố vấn học tập.', 'error');
        return;
      }

      const classes = Array.from(state.selectedClasses);
      if (!classes.length) {
        message('Không có lớp nào được chọn.', 'error');
        return;
      }

      const submitBtn = $('[data-btn-save-batch]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const promises = classes.map(cls => request('/advisor-assignments', {
          method: 'POST',
          body: JSON.stringify({ advisor_username: advisorUsername, academic_class: cls })
        }));
        await Promise.all(promises);

        state.selectedClasses.clear();
        form.closest('dialog')?.close();
        await loadAll();
        message(`Đã phân công thành công cho ${classes.length} lớp.`);
      } catch (err) {
        message(err.message, 'error');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    // 17. Submit các form khác (relation, program)
    $$('[data-form]:not([data-form="assignment"]):not([data-form="batch-assignment"]):not([data-form="course"]):not([data-course-form])').forEach(form => {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const d = Object.fromEntries(new FormData(form));
        try {
          if (form.dataset.form === 'relation') {
            await request(`/relations/${d.relation}`, { method: 'PUT', body: JSON.stringify({ ...d, enabled: true }) });
          }
          if (form.dataset.form === 'program') {
            await request(d.mode === 'edit' ? `/programs/${encodeURIComponent(d.program_id)}` : '/programs', {
              method: d.mode === 'edit' ? 'PUT' : 'POST',
              body: JSON.stringify(d)
            });
          }
          form.closest('dialog')?.close();
          form.reset();
          await loadAll();
          message('Đã lưu thay đổi.');
        } catch (err) {
          message(err.message, 'error');
        }
      });
    });

    // 18. Các sự kiện Click tổng hợp: Phân công lớp, Xem DS SV, Gỡ cố vấn, v.v.
    document.addEventListener('click', async e => {
      // Mở modal phân công cố vấn
      const detailBtn = e.target.closest('[data-class-detail]');
      if (detailBtn) {
        openClassModal(detailBtn.dataset.classDetail);
        return;
      }

      // Xem danh sách sinh viên khi bấm vào số lượng sinh viên hoặc nút xem
      const viewRosterBtn = e.target.closest('[data-action="view-roster"]') || e.target.closest('[data-view-students]');
      if (viewRosterBtn) {
        const cls = viewRosterBtn.dataset.class || viewRosterBtn.dataset.viewStudents;
        openRosterModal(cls);
        return;
      }

      // Chỉnh sửa chương trình đào tạo
      const editProgram = e.target.closest('[data-edit-program]');
      if (editProgram) {
        const f = $('[data-form="program"]');
        f.reset();
        f.mode.value = 'edit';
        f.program_id.value = editProgram.dataset.editProgram;
        f.program_id.readOnly = true;
        f.name.value = editProgram.dataset.programName;
        $('[data-program-dialog-title]').textContent = 'Cập nhật chương trình đào tạo';
        $('[data-program-submit]').textContent = 'Lưu cập nhật';
        $('[data-dialog="program"]').showModal();
        return;
      }

      // Xóa quan hệ / Lưu trữ CTĐT / Gỡ cố vấn
      const removeRel = e.target.closest('[data-remove-relation]');
      const archiveProg = e.target.closest('[data-archive-program]');
      const revokeAdv = e.target.closest('[data-revoke-advisor]');

      if (!removeRel && !archiveProg && !revokeAdv) return;

      const confirmMsg = revokeAdv
        ? `Gỡ cố vấn ${revokeAdv.dataset.revokeAdvisor} khỏi lớp ${revokeAdv.dataset.academicClass}?`
        : 'Bạn có chắc chắn muốn thực hiện thao tác này?';

      if (!confirm(confirmMsg)) return;

      try {
        if (removeRel) {
          await request(`/relations/${removeRel.dataset.type}`, {
            method: 'PUT',
            body: JSON.stringify({
              course_code: removeRel.dataset.course,
              related_course_code: removeRel.dataset.related,
              enabled: false
            })
          });
        }
        if (archiveProg) {
          await request(`/programs/${encodeURIComponent(archiveProg.dataset.archiveProgram)}`, { method: 'DELETE' });
        }
        if (revokeAdv) {
          await request('/advisor-assignments', {
            method: 'DELETE',
            body: JSON.stringify({
              advisor_username: revokeAdv.dataset.revokeAdvisor,
              academic_class: revokeAdv.dataset.academicClass
            })
          });
        }
        await loadAll();
        message('Đã cập nhật dữ liệu.');
      } catch (err) {
        message(err.message, 'error');
      }
    });

    // 19. Gỡ cố vấn từ bên trong modal chi tiết
    $('[data-remove-current-advisor]')?.addEventListener('click', async () => {
      const row = state.currentClass;
      if (!row || !row.assignment || !confirm(`Gỡ cố vấn của lớp ${row.academic_class}?`)) return;

      try {
        await request('/advisor-assignments', {
          method: 'DELETE',
          body: JSON.stringify({
            advisor_username: row.assignment.advisor_username,
            academic_class: row.academic_class
          })
        });
        $('[data-dialog="assignment"]')?.close();
        await loadAll();
        message('Đã gỡ cố vấn thành công.');
      } catch (err) {
        message(err.message, 'error');
      }
    });

    // Khởi tạo tải dữ liệu
    loadAll();
  });
})();
