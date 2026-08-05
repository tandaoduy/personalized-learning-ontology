(function () {
    function createSidebar({ brand = "", links = [], footer = null } = {}) {
        const sidebar = document.createElement("aside");
        sidebar.className = "ui-sidebar";

        const brandEl = document.createElement("div");
        brandEl.className = "ui-sidebar__brand";
        brandEl.textContent = brand;

        const nav = document.createElement("nav");
        nav.className = "ui-sidebar__nav";
        links.forEach((link) => {
            const a = document.createElement("a");
            a.className = `ui-sidebar__link${link.active ? " is-active" : ""}`;
            a.href = link.href || "#";
            a.textContent = link.label || "";
            nav.appendChild(a);
        });

        sidebar.append(brandEl, nav);
        if (footer) {
            const footerEl = document.createElement("div");
            footerEl.className = "ui-sidebar__footer";
            footerEl.append(footer instanceof Node ? footer : document.createTextNode(footer));
            sidebar.appendChild(footerEl);
        }
        return sidebar;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createSidebar = createSidebar;
})();
