(function () {
    function createToggle({ checked = false, label = "", onChange } = {}) {
        const wrapper = document.createElement("label");
        wrapper.className = "ui-toggle";

        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(checked);

        const track = document.createElement("span");
        track.className = "ui-toggle__track";

        const thumb = document.createElement("span");
        thumb.className = "ui-toggle__thumb";

        const text = document.createElement("span");
        text.className = "ui-toggle__label";
        text.textContent = label;

        track.appendChild(thumb);
        wrapper.append(input, track, text);

        if (typeof onChange === "function") {
            input.addEventListener("change", () => onChange(input.checked, input));
        }

        return wrapper;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createToggle = createToggle;
})();
