(function () {
    function createBadge({ label = "", variant = "neutral", dot = false } = {}) {
        const badge = document.createElement("span");
        badge.className = [
            "ui-badge",
            `ui-badge--${variant}`,
            dot ? "ui-badge--dot" : "",
        ].filter(Boolean).join(" ");
        badge.textContent = label;
        return badge;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createBadge = createBadge;
})();
