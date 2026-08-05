(function () {
    function createTabs({ tabs = [] } = {}) {
        const root = document.createElement("div");
        root.className = "ui-tabs";

        const list = document.createElement("div");
        list.className = "ui-tabs__list";
        list.setAttribute("role", "tablist");

        const panels = document.createElement("div");
        panels.className = "ui-tabs__panels";

        tabs.forEach((tab, index) => {
            const id = `ui-tab-${Date.now()}-${index}`;
            const button = document.createElement("button");
            button.type = "button";
            button.className = `ui-tabs__tab${index === 0 ? " is-active" : ""}`;
            button.setAttribute("role", "tab");
            button.setAttribute("aria-controls", id);
            button.textContent = tab.label || `Tab ${index + 1}`;

            const panel = document.createElement("div");
            panel.id = id;
            panel.className = `ui-tabs__panel${index === 0 ? " is-active" : ""}`;
            panel.setAttribute("role", "tabpanel");
            panel.append(tab.content instanceof Node ? tab.content : document.createTextNode(tab.content || ""));

            button.addEventListener("click", () => {
                root.querySelectorAll(".ui-tabs__tab, .ui-tabs__panel").forEach((el) => el.classList.remove("is-active"));
                button.classList.add("is-active");
                panel.classList.add("is-active");
            });

            list.appendChild(button);
            panels.appendChild(panel);
        });

        root.append(list, panels);
        return root;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createTabs = createTabs;
})();
