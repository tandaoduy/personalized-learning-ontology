window.UIComponents = window.UIComponents || {};

window.addEventListener("DOMContentLoaded", () => {
    if (!window.showToast && window.UIComponents.showAlert) {
        window.showToast = (message, type = "info", duration = 3200) => {
            const normalizedType = type === "danger" ? "error" : type;
            return window.UIComponents.showAlert(message, {
                type: normalizedType,
                duration,
            });
        };
    }
});

/* Scroll Reveal Effect */
window.addEventListener("DOMContentLoaded", () => {
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("revealed");
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });
    document.querySelectorAll(".reveal-up").forEach(el => revealObserver.observe(el));
});
