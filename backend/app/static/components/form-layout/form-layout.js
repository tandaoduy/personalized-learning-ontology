(function () {
    function createField({ label = "", type = "text", name = "", placeholder = "", value = "", options = [] } = {}) {
        const field = document.createElement("div");
        field.className = "ui-field";
        field.dataset.fieldName = name;

        const labelEl = document.createElement("label");
        labelEl.textContent = label;

        const input = document.createElement(type === "textarea" ? "textarea" : type === "select" ? "select" : "input");
        if (type !== "textarea" && type !== "select") {
            input.type = type;
        }
        if (type === "select") {
            options.forEach((option) => {
                const optionEl = document.createElement("option");
                optionEl.value = option.value || "";
                optionEl.textContent = option.label || option.value || "";
                input.appendChild(optionEl);
            });
        }
        input.name = name;
        input.placeholder = placeholder;
        input.value = value;

        const error = document.createElement("p");
        error.className = "ui-field__error";
        error.hidden = true;

        field.append(labelEl, input, error);
        return field;
    }

    function createFormLayout({ twoColumns = false, children = [] } = {}) {
        const form = document.createElement("form");
        form.className = `ui-form${twoColumns ? " ui-form--two-columns" : ""}`;
        children.forEach((child) => form.appendChild(child));
        return form;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createField = createField;
    window.UIComponents.createFormLayout = createFormLayout;
})();
