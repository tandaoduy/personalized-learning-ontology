(function () {
    function createButton({ label = "", variant = "primary", size = "", icon = null, onClick } = {}) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = ["ui-btn", variant !== "primary" ? `ui-btn--${variant}` : "", size ? `ui-btn--${size}` : ""]
            .filter(Boolean)
            .join(" ");

        if (icon) {
            const iconSpan = document.createElement("span");
            iconSpan.className = "ui-btn__icon";
            iconSpan.innerHTML = icon;
            button.appendChild(iconSpan);
        }

        const labelSpan = document.createElement("span");
        labelSpan.textContent = label;
        button.appendChild(labelSpan);

        if (typeof onClick === "function") {
            button.addEventListener("click", onClick);
        }

        return button;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createButton = createButton;
})();
