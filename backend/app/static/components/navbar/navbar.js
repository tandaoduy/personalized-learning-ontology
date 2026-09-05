(function () {
    function createNavbar({ brand = "", links = [], actions = null } = {}) {
        const nav = document.createElement("header");
        nav.className = "ui-navbar";

        const brandEl = document.createElement("a");
        brandEl.className = "ui-navbar__brand";
        brandEl.href = "/";
        brandEl.textContent = brand;

        const linksEl = document.createElement("nav");
        linksEl.className = "ui-navbar__links";
        links.forEach((link) => {
            const a = document.createElement("a");
            a.className = `ui-navbar__link${link.active ? " is-active" : ""}`;
            a.href = link.href || "#";
            a.textContent = link.label || "";
            linksEl.appendChild(a);
        });

        nav.append(brandEl, linksEl);
        if (actions) {
            nav.append(actions instanceof Node ? actions : document.createTextNode(actions));
        }
        return nav;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createNavbar = createNavbar;
})();
