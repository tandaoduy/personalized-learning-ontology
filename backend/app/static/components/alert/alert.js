(function () {
    function ensureToastRegion() {
        let region = document.querySelector("[data-ui-toast-region]");
        if (!region) {
            region = document.createElement("div");
            region.className = "ui-toast-region";
            region.dataset.uiToastRegion = "true";
            region.setAttribute("aria-live", "polite");
            region.setAttribute("aria-atomic", "true");
            if ("popover" in HTMLElement.prototype) {
                region.setAttribute("popover", "manual");
            }
            document.body.appendChild(region);
        }

        if (region.showPopover && !region.matches(":popover-open")) {
            try { region.showPopover(); } catch(e) {}
        } else if (!("popover" in HTMLElement.prototype)) {
            const openDialog = document.querySelector("dialog[open]");
            if (openDialog && region.parentNode !== openDialog) {
                openDialog.appendChild(region);
            } else if (!openDialog && region.parentNode !== document.body) {
                document.body.appendChild(region);
            }
        }

        return region;
    }

    function removeAlert(alert) {
        if (!alert || alert.dataset.state === "leaving") {
            return;
        }

        alert.dataset.state = "leaving";
        window.setTimeout(() => alert.remove(), 220);
    }

    function showAlert(message, options = {}) {
        if (!message) {
            return null;
        }

        const type = options.type || "info";
        const duration = Number(options.duration ?? 3200);
        const region = ensureToastRegion();
        const alert = document.createElement("div");
        alert.className = `ui-alert ui-alert--${type}`;
        alert.setAttribute("role", type === "error" ? "alert" : "status");

        const iconSvg = {
            success: `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" class="ui-alert__icon-svg"><circle cx="12" cy="12" r="10" fill="#22c55e" stroke="none"></circle><path stroke="#fff" stroke-linecap="round" stroke-linejoin="round" d="M8 12.5l3 3 5-6"></path></svg>`,
            error: `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" class="ui-alert__icon-svg"><circle cx="12" cy="12" r="10" fill="#ef4444" stroke="none"></circle><path stroke="#fff" stroke-linecap="round" stroke-linejoin="round" d="M15 9l-6 6m0-6l6 6"></path></svg>`,
            warning: `<svg fill="none" viewBox="0 0 24 24" class="ui-alert__icon-svg" aria-hidden="true"><path d="M10.27 3.72a2 2 0 0 1 3.46 0l8 14A2 2 0 0 1 20 20.72H4a2 2 0 0 1-1.73-3l8-14Z" fill="#f59e0b"></path><path d="M12 8v5" stroke="#fff" stroke-width="2.25" stroke-linecap="round"></path><circle cx="12" cy="16.5" r="1.15" fill="#fff"></circle></svg>`,
            info: `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" class="ui-alert__icon-svg"><circle cx="12" cy="12" r="10" fill="#3b82f6" stroke="none"></circle><path stroke="#fff" stroke-linecap="round" stroke-linejoin="round" d="M12 16v-4m0-4h.01"></path></svg>`
        };

        const iconContainer = document.createElement("div");
        iconContainer.className = "ui-alert__icon";
        iconContainer.innerHTML = iconSvg[type] || iconSvg['info'];

        const close = document.createElement("button");
        close.className = "ui-alert__close";
        close.type = "button";
        close.setAttribute("aria-label", "Đóng thông báo");
        close.innerHTML = "&times;";

        const content = document.createElement("div");
        content.className = "ui-alert__message";
        content.textContent = message;

        const progressTrack = document.createElement("div");
        progressTrack.className = "ui-alert__progress-track";
        const progress = document.createElement("div");
        progress.className = "ui-alert__progress";
        progress.style.animationDuration = `${duration}ms`;
        progressTrack.appendChild(progress);

        close.addEventListener("click", () => removeAlert(alert));
        alert.append(iconContainer, content, close, progressTrack);
        region.appendChild(alert);

        if (duration > 0) {
            window.setTimeout(() => removeAlert(alert), duration);
        }

        return alert;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.showAlert = showAlert;
})();
