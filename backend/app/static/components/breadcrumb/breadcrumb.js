(function () {
    const ICON_MAP = {
        home: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        user: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
        filter: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>',
        alert: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        file: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
        check: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
        report: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
        users: '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        'user-plus': '<svg class="ui-breadcrumb__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>'
    };

    function getIconHTML(icon) {
        if (!icon) return '';
        if (ICON_MAP[icon]) return ICON_MAP[icon];
        if (icon.trim().startsWith('<svg')) return icon;
        return `<span class="ui-breadcrumb__icon" aria-hidden="true">${icon}</span>`;
    }

    function createBreadcrumb({ items = [], separator = "/" } = {}) {
        const nav = document.createElement("nav");
        nav.className = "ui-breadcrumb";
        nav.setAttribute("aria-label", "Breadcrumb");

        const ol = document.createElement("ol");
        ol.className = "ui-breadcrumb__list";

        items.forEach((item, index) => {
            const isLast = index === items.length - 1;
            const label = typeof item === "string" ? item : (item.label || "");
            const href = typeof item === "string" ? null : item.href;
            const icon = typeof item === "string" ? null : item.icon;

            const li = document.createElement("li");
            li.className = "ui-breadcrumb__item";

            if (isLast || !href) {
                const span = document.createElement("span");
                span.className = "ui-breadcrumb__current";
                span.setAttribute("aria-current", "page");
                if (icon) {
                    span.innerHTML = getIconHTML(icon) + ` <span>${label}</span>`;
                } else {
                    span.textContent = label;
                }
                li.appendChild(span);
            } else {
                const a = document.createElement("a");
                a.className = "ui-breadcrumb__link";
                a.href = href;
                if (icon) {
                    a.innerHTML = getIconHTML(icon) + ` <span>${label}</span>`;
                } else {
                    a.textContent = label;
                }
                li.appendChild(a);
            }

            ol.appendChild(li);

            if (!isLast) {
                const sepLi = document.createElement("li");
                sepLi.className = "ui-breadcrumb__separator";
                sepLi.setAttribute("aria-hidden", "true");
                sepLi.textContent = separator;
                ol.appendChild(sepLi);
            }
        });

        nav.appendChild(ol);
        return nav;
    }

    // Auto initialize declarative breadcrumbs
    function initAllBreadcrumbs() {
        document.querySelectorAll(".ui-breadcrumb[data-breadcrumb]").forEach(el => {
            if (el.children.length > 0) return; // Không ghi đè nếu đã có HTML fallback tĩnh
            el.replaceChildren();
            try {
                const items = JSON.parse(el.getAttribute("data-breadcrumb"));
                const sep = el.getAttribute("data-separator") || "/";
                const breadcrumbNav = createBreadcrumb({ items, separator: sep });
                el.innerHTML = breadcrumbNav.innerHTML;
            } catch (e) {
                console.error("Error initializing declarative breadcrumb:", e);
            }
        });
    }

    if (document.readyState === "loading") {
        window.addEventListener("DOMContentLoaded", initAllBreadcrumbs);
    } else {
        initAllBreadcrumbs();
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createBreadcrumb = createBreadcrumb;
})();
