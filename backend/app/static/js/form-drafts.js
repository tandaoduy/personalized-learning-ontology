(function () {
    function getKey(form) {
        return `form-draft:${window.location.pathname}${window.location.search}:${form.id}`;
    }

    function readValues(form) {
        return Array.from(form.elements)
            .filter((field) => field.name && !field.disabled && !field.readOnly && !["password", "file", "submit", "button"].includes(field.type))
            .reduce((values, field) => {
                if (field.type === "checkbox" || field.type === "radio") {
                    if (field.checked) values[field.name] = field.value;
                } else {
                    values[field.name] = field.value;
                }
                return values;
            }, {});
    }

    function save(form) {
        try {
            sessionStorage.setItem(getKey(form), JSON.stringify(readValues(form)));
        } catch (_) {}
    }

    function clear(form) {
        try { sessionStorage.removeItem(getKey(form)); } catch (_) {}
    }

    function restore(form) {
        let values;
        try { values = JSON.parse(sessionStorage.getItem(getKey(form)) || "null"); } catch (_) { return; }
        if (!values) return;
        Object.entries(values).forEach(([name, value]) => {
            const fields = form.querySelectorAll(`[name="${CSS.escape(name)}"]`);
            fields.forEach((field) => {
                if (field.type === "checkbox" || field.type === "radio") {
                    field.checked = field.value === value;
                } else if (Array.from(field.options || []).some((option) => option.value === value) || field.tagName !== "SELECT") {
                    field.value = value;
                }
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("form[data-preserve-draft]").forEach((form) => {
            restore(form);
            form.addEventListener("input", () => save(form));
            form.addEventListener("change", () => save(form));
            // Profile data loaded asynchronously may replace field values after DOMContentLoaded.
            window.setTimeout(() => restore(form), 900);
        });

        document.addEventListener("form-drafts:clear", (event) => {
            if (event.detail?.form instanceof HTMLFormElement) clear(event.detail.form);
        });
    });
})();
