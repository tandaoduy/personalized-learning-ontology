(function () {
    function createDropdown({ trigger, items = [] } = {}) {
        const root = document.createElement("div");
        root.className = "ui-dropdown";

        const triggerEl = trigger instanceof Node ? trigger : document.createElement("button");
        if (!(trigger instanceof Node)) {
            triggerEl.type = "button";
            triggerEl.className = "ui-btn ui-btn--secondary";
            triggerEl.textContent = trigger || "Mở menu";
        }

        const menu = document.createElement("div");
        menu.className = "ui-dropdown__menu";
        menu.hidden = true;

        items.forEach((item) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ui-dropdown__item";
            button.textContent = item.label || "";
            button.addEventListener("click", () => {
                menu.hidden = true;
                item.onClick?.(item);
            });
            menu.appendChild(button);
        });

        triggerEl.addEventListener("click", (event) => {
            event.stopPropagation();
            menu.hidden = !menu.hidden;
        });

        document.addEventListener("click", (event) => {
            if (!root.contains(event.target)) {
                menu.hidden = true;
            }
        });

        root.append(triggerEl, menu);
        return root;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createDropdown = createDropdown;
})();
