(function () {
    function getInitials(name) {
        return String(name || "")
            .trim()
            .split(/\s+/)
            .slice(-2)
            .map((part) => part[0])
            .join("")
            .toUpperCase() || "U";
    }

    function createAvatar({ name = "", src = "", size = "" } = {}) {
        const avatar = document.createElement("span");
        avatar.className = ["ui-avatar", size ? `ui-avatar--${size}` : ""].filter(Boolean).join(" ");
        avatar.title = name;

        if (src) {
            const img = document.createElement("img");
            img.src = src;
            img.alt = name;
            avatar.appendChild(img);
        } else {
            avatar.textContent = getInitials(name);
        }

        return avatar;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createAvatar = createAvatar;
})();
