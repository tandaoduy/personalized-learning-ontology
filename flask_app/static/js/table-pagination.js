(function () {
    const PAGE_SIZES = [10, 20, 50, 100, "all"];
    const states = new WeakMap();

    function getRows(table) {
        const body = table.tBodies[0];
        if (!body) return [];
        return Array.from(body.rows).filter((row) => {
            const firstCell = row.cells[0];
            return !(row.cells.length === 1 && firstCell && firstCell.colSpan > 1);
        });
    }

    function buildPageButtons(state, totalPages) {
        const fragment = document.createDocumentFragment();
        const start = Math.max(1, state.page - 2);
        const end = Math.min(totalPages, start + 4);
        for (let page = start; page <= end; page += 1) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "app-pagination__page" + (page === state.page ? " is-active" : "");
            button.textContent = String(page);
            button.setAttribute("aria-label", `Trang ${page}`);
            button.addEventListener("click", () => {
                state.page = page;
                render(state);
            });
            fragment.append(button);
        }
        return fragment;
    }

    function render(state) {
        const rows = getRows(state.table);
        const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
        state.page = Math.min(Math.max(1, state.page), totalPages);
        const first = (state.page - 1) * state.pageSize;
        const last = first + state.pageSize;

        rows.forEach((row, index) => { row.hidden = index < first || index >= last; });
        const summaryText = rows.length
            ? `Hiển thị ${first + 1}-${Math.min(last, rows.length)} / ${rows.length} dòng`
            : "Không có dữ liệu";
        state.previous.disabled = state.page === 1;
        state.next.disabled = state.page === totalPages;
        state.pages.replaceChildren(buildPageButtons(state, totalPages));
        state.controls.hidden = rows.length === 0;
    }

    function createPagination(table) {
        if (states.has(table) || table.dataset.pagination === "off" || table.classList.contains("print-table")) return;
        const body = table.tBodies[0];
        if (!body) return;

        const controls = document.createElement("nav");
        controls.className = "app-pagination";
        controls.setAttribute("aria-label", "Phân trang bảng dữ liệu");
        controls.innerHTML = `
            <label class="app-pagination__size" style="white-space: nowrap; display: flex; align-items: center; gap: 6px;">Hiển thị
                <select aria-label="Số dòng mỗi trang">${PAGE_SIZES.map((size) => `<option value="${size}">${size === "all" ? "Tất cả" : size}</option>`).join("")}</select>
                dòng/trang
            </label>
            <div class="app-pagination__actions">
                <button type="button" class="app-pagination__nav" data-page="previous" aria-label="Trang trước">&lt;</button>
                <span class="app-pagination__pages"></span>
                <button type="button" class="app-pagination__nav" data-page="next" aria-label="Trang sau">&gt;</button>
            </div>`;

        table.insertAdjacentElement("afterend", controls);
        const state = {
            table,
            controls,
            page: 1,
            pageSize: 10,
            pages: controls.querySelector(".app-pagination__pages"),
            previous: controls.querySelector('[data-page="previous"]'),
            next: controls.querySelector('[data-page="next"]'),
        };
        states.set(table, state);

        controls.querySelector("select").addEventListener("change", (event) => {
            state.pageSize = event.target.value === "all" ? Infinity : Number(event.target.value);
            state.page = 1;
            render(state);
        });
        state.previous.addEventListener("click", () => { state.page -= 1; render(state); });
        state.next.addEventListener("click", () => { state.page += 1; render(state); });
        new MutationObserver(() => {
            state.page = 1;
            render(state);
        }).observe(body, { childList: true });
        render(state);
    }

    function initialize() {
        document.querySelectorAll("main table").forEach(createPagination);
    }

    document.addEventListener("DOMContentLoaded", initialize);
    new MutationObserver(initialize).observe(document.documentElement, { childList: true, subtree: true });
})();
