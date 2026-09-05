(function () {
    function createAuthCard({
        mode = "login",
        title = "",
        description = "",
        badge = "",
        fields = [],
        submitLabel = "",
        footerText = "",
        footerActionLabel = "",
        onSubmit,
        onFooterAction,
    } = {}) {
        const card = document.createElement("section");
        card.className = "ui-auth-card";
        card.dataset.authMode = mode;

        const header = document.createElement("header");
        header.className = "ui-auth-card__header";

        if (badge) {
            const badgeEl = document.createElement("p");
            badgeEl.className = "ui-auth-card__badge";
            badgeEl.textContent = badge;
            header.appendChild(badgeEl);
        }

        const heading = document.createElement("h1");
        heading.className = "ui-auth-card__title";
        heading.textContent = title;

        const desc = document.createElement("p");
        desc.className = "ui-auth-card__description";
        desc.textContent = description;

        header.append(heading, desc);

        const form = document.createElement("form");
        form.className = "ui-auth-card__form";

        fields.forEach((field) => {
            const fieldEl = window.UIComponents?.createField
                ? window.UIComponents.createField(field)
                : null;
            if (fieldEl) {
                form.appendChild(fieldEl);
            }
        });

        const submit = window.UIComponents?.createButton
            ? window.UIComponents.createButton({ label: submitLabel, variant: "primary" })
            : document.createElement("button");
        submit.type = "submit";
        if (!window.UIComponents?.createButton) {
            submit.textContent = submitLabel;
        }
        form.appendChild(submit);

        function clearFieldErrors() {
            form.querySelectorAll(".ui-field.has-error").forEach((field) => {
                field.classList.remove("has-error");
                const error = field.querySelector(".ui-field__error");
                if (error) {
                    error.textContent = "";
                    error.hidden = true;
                }
            });
        }

        function showFieldError(fieldName, message) {
            const field = form.querySelector(`.ui-field[data-field-name="${fieldName}"]`);
            if (!field) {
                return false;
            }
            field.classList.add("has-error");
            const error = field.querySelector(".ui-field__error");
            if (error) {
                error.textContent = message || "Vui lòng kiểm tra lại thông tin.";
                error.hidden = false;
            }
            return true;
        }

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            const data = Object.fromEntries(new FormData(form).entries());
            clearFieldErrors();

            const emptyFields = fields.filter((field) => {
                if (field.required === false) {
                    return false;
                }
                return !String(data[field.name] || "").trim();
            });
            if (emptyFields.length) {
                emptyFields.forEach((field) => {
                    const message = `Vui lòng nhập ${String(field.label || "đầy đủ thông tin").toLowerCase()}.`;
                    showFieldError(field.name, message);
                });
                form.querySelector(`[name="${emptyFields[0].name}"]`)?.focus();
                return;
            }

            onSubmit?.(data, form, {
                showError(message) {
                    const target = data.password ? "username" : "password";
                    showFieldError(target, message || "Vui lòng kiểm tra lại thông tin.");
                },
                showFieldError,
                clearFieldErrors,
                clearError() {
                    clearFieldErrors();
                },
            });
        });

        card.append(header, form);

        if (footerText || footerActionLabel) {
            const footer = document.createElement("p");
            footer.className = "ui-auth-card__footer";
            footer.append(document.createTextNode(footerText ? `${footerText} ` : ""));

            if (footerActionLabel) {
                const action = document.createElement("button");
                action.type = "button";
                action.textContent = footerActionLabel;
                action.addEventListener("click", () => onFooterAction?.());
                footer.appendChild(action);
            }

            card.appendChild(footer);
        }
        return card;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createAuthCard = createAuthCard;
})();
