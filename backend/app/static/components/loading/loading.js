(function () {
    function resolve(target) {
        return typeof target === 'string' ? document.getElementById(target) : target;
    }

    function setLoading(target, isLoading, message) {
        const el = resolve(target);
        if (!el) return;
        el.classList.toggle('is-active', Boolean(isLoading));
        el.setAttribute('aria-hidden', isLoading ? 'false' : 'true');
        const messageEl = el.querySelector('[data-loading-message]');
        if (message && messageEl) messageEl.textContent = message;
    }

    function initAll() {
        document.querySelectorAll('[data-ui-loading]').forEach((el) => {
            if (el.dataset.loadingReady === 'true') return;
            const title = el.dataset.loadingTitle || 'Đang tải dữ liệu';
            const message = el.dataset.loadingMessage || 'Vui lòng chờ trong giây lát...';
            el.classList.add('ui-loading');
            el.setAttribute('role', 'status');
            el.setAttribute('aria-live', 'polite');
            el.setAttribute('aria-hidden', 'true');
            el.innerHTML = `<span class="ui-loading__paw-track" aria-hidden="true"><span class="ui-loading__paw">🐾</span></span><div class="ui-loading__content"><strong class="ui-loading__title"></strong><span class="ui-loading__message" data-loading-message></span></div>`;
            el.querySelector('.ui-loading__title').textContent = title;
            el.querySelector('[data-loading-message]').textContent = message;
            el.dataset.loadingReady = 'true';
        });
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.setLoading = setLoading;
    window.UIComponents.initLoading = initAll;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
