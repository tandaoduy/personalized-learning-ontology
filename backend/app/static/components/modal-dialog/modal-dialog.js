(function () {
    function closeModal(backdrop) {
        backdrop.remove();
        document.body.style.overflow = "";
    }

    function createModalDialog({ title = "", description = "", content = "", actions = [], size = "md" } = {}) {
        const backdrop = document.createElement("div");
        backdrop.className = "ui-modal-backdrop";

        const modal = document.createElement("section");
        modal.className = `ui-modal ui-modal--${size}`;
        modal.setAttribute("role", "dialog");
        modal.setAttribute("aria-modal", "true");

        const header = document.createElement("header");
        header.className = "ui-modal__header";

        const headingWrap = document.createElement("div");
        const heading = document.createElement("h2");
        heading.className = "ui-modal__title";
        heading.textContent = title;
        headingWrap.appendChild(heading);

        if (description) {
            const desc = document.createElement("p");
            desc.className = "ui-modal__description";
            desc.textContent = description;
            headingWrap.appendChild(desc);
        }

        const close = document.createElement("button");
        close.className = "ui-modal__close";
        close.type = "button";
        close.setAttribute("aria-label", "Đóng hộp thoại");
        close.innerHTML = "&times;";
        
        header.append(headingWrap, close);
        modal.append(header);

        if (content) {
            const body = document.createElement("div");
            body.className = "ui-modal__body";
            body.append(content instanceof Node ? content : document.createTextNode(content));
            modal.append(body);
        } else {
            header.style.borderBottom = "none";
        }

        const footer = document.createElement("footer");
        footer.className = "ui-modal__footer";
        actions.forEach((action) => {
            const button = window.UIComponents?.createButton
                ? window.UIComponents.createButton(action)
                : document.createElement("button");
            if (!window.UIComponents?.createButton) {
                button.type = "button";
                button.textContent = action.label || "";
            }
            button.addEventListener("click", () => {
                action.onClick?.();
                if (action.close !== false) {
                    closeModal(backdrop);
                }
            });
            footer.appendChild(button);
        });

        close.addEventListener("click", () => closeModal(backdrop));
        backdrop.addEventListener("click", (event) => {
            if (event.target === backdrop) {
                closeModal(backdrop);
            }
        });

        if (actions.length) {
            modal.appendChild(footer);
        }
        backdrop.appendChild(modal);

        return backdrop;
    }

    function showModalDialog(options = {}) {
        const modal = createModalDialog(options);
        document.body.appendChild(modal);
        document.body.style.overflow = "hidden";
        modal.querySelector(".ui-modal__close")?.focus();
        return modal;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createModalDialog = createModalDialog;
    window.UIComponents.showModalDialog = showModalDialog;
})();
