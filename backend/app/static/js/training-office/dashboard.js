/**
 * JavaScript Quản trị học vụ - Phòng Đào tạo (Training Office)
 * Cung cấp đầy đủ tính năng: Quan hệ học phần, CTĐT, Phân công cố vấn hiện đại (KPIs, Batch Assign, Interactive Cards, Student Roster)
 */
(() => {
  const api = '/api/training-office';
  const state = {
    relations: [],
    programs: [],
    assignments: [],
    advisors: [],
    selectedClasses: new Set(),
    filterStatus: 'all',
    filterCohort: 'all',
    searchQuery: '',
    currentClass: null,
    currentTab: 'assign',
    rosterQuery: ''
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
            <div class="to-student-pill">
              <i data-lucide="users"></i>
              <span>${item.student_count} sinh viên</span>
            </div>
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

  // Mở Modal Chi tiết & Phân công Lớp
  function openClassModal(academicClass, defaultTab = 'assign') {
    const row = state.assignments.find(x => x.academic_class === academicClass);
    if (!row) return;

    state.currentClass = row;
    state.currentTab = defaultTab;
    state.rosterQuery = '';

    const dialog = $('[data-dialog="assignment"]');
    if (!dialog) return;

    // Header thông tin
    $('[data-modal-class-title]').textContent = `Lớp ${row.academic_class}`;
    $('[data-modal-student-count]').textContent = row.student_count;
    $('[data-modal-tab-student-count]').textContent = row.student_count;
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

    // Render Danh sách sinh viên
    renderStudentRoster(row.students || []);

    // Active tab
    switchModalTab(defaultTab);

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

    const q = state.rosterQuery.toLowerCase().trim();
    const filtered = (students || []).filter(s => {
      if (!q) return true;
      return (s.name || '').toLowerCase().includes(q) || (s.student_id || '').toLowerCase().includes(q);
    });

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="to-loading">Không tìm thấy sinh viên phù hợp.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map((s, idx) => `
      <tr>
        <td style="color:#64748b;font-weight:600;">${idx + 1}</td>
        <td><strong style="color:#0f172a;font-family:monospace;">${esc(s.student_id)}</strong></td>
        <td><strong>${esc(s.name)}</strong></td>
        <td>${esc(s.major || 'Công nghệ thông tin')}</td>
        <td style="text-align:center;"><span class="to-badge to-badge--blue">Kỳ ${esc(s.semester || 1)}</span></td>
      </tr>
    `).join('');
  }

  function switchModalTab(tabName) {
    state.currentTab = tabName;
    $$('[data-modal-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.modalTab === tabName);
    });

    const assignContent = $('[data-tab-content="assign"]');
    const studentsContent = $('[data-tab-content="students"]');
    if (assignContent && studentsContent) {
      assignContent.style.display = tabName === 'assign' ? 'block' : 'none';
      studentsContent.style.display = tabName === 'students' ? 'block' : 'none';
    }
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

      await Promise.all([
        load('relations', '/relations'),
        load('programs', '/programs'),
        advisorsPromise
      ]);

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
      if (dialog) dialog.showModal();
    }));

    // 2. Đóng modals khi click nút data-modal-close
    $$('[data-modal-close]').forEach(btn => {
      btn.addEventListener('click', () => {
        const dialog = btn.closest('dialog');
        if (dialog) dialog.close();
      });
    });

    // 3. Chuyển tab trong Assignment Modal
    $$('[data-modal-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        switchModalTab(btn.dataset.modalTab);
      });
    });

    // 4. Lọc tìm kiếm sinh viên trong Roster Tab
    $('[data-roster-filter]')?.addEventListener('input', (e) => {
      state.rosterQuery = e.target.value;
      if (state.currentClass) {
        renderStudentRoster(state.currentClass.students || []);
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

    // Lọc cho relations và programs
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

    // 14. Nút Làm mới (Refresh)
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
        // Thực thi phân công lần lượt cho các lớp được chọn
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
    $$('[data-form]:not([data-form="assignment"]):not([data-form="batch-assignment"])').forEach(form => {
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

    // 18. Các sự kiện Click tổng hợp: Chi tiết lớp, Xem SV, Gỡ cố vấn, v.v.
    document.addEventListener('click', async e => {
      // Mở modal phân công / chi tiết
      const detailBtn = e.target.closest('[data-class-detail]');
      if (detailBtn) {
        openClassModal(detailBtn.dataset.classDetail, 'assign');
        return;
      }

      // Xem danh sách sinh viên
      const viewStudentsBtn = e.target.closest('[data-view-students]');
      if (viewStudentsBtn) {
        openClassModal(viewStudentsBtn.dataset.viewStudents, 'students');
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
