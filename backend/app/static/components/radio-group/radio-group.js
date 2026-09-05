(function () {
    function createRadioGroup({ name = "radio-group", options = [], value = "", onChange } = {}) {
        const group = document.createElement("div");
        group.className = "ui-radio-group";

        options.forEach((option) => {
            const label = document.createElement("label");
            label.className = "ui-radio-card";

            const input = document.createElement("input");
            input.type = "radio";
            input.name = name;
            input.value = option.value;
            input.checked = option.value === value;

            const content = document.createElement("span");
            content.className = "ui-radio-card__content";
            const title = document.createElement("span");
            title.className = "ui-radio-card__label";
            title.textContent = option.label || "";
            const description = document.createElement("span");
            description.className = "ui-radio-card__description";
            description.textContent = option.description || "";
            content.append(title, description);

            input.addEventListener("change", () => onChange?.(input.value, input));
            label.append(input, content);
            group.appendChild(label);
        });

        return group;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createRadioGroup = createRadioGroup;
})();
