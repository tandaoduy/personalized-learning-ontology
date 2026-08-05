(function () {
    function createCard({ title = "", description = "", image = "", footer = null } = {}) {
        const card = document.createElement("article");
        card.className = "ui-card";

        if (image) {
            const img = document.createElement("img");
            img.className = "ui-card__media";
            img.src = image;
            img.alt = title;
            card.appendChild(img);
        }

        const body = document.createElement("div");
        body.className = "ui-card__body";

        const heading = document.createElement("h3");
        heading.className = "ui-card__title";
        heading.textContent = title;

        const text = document.createElement("p");
        text.className = "ui-card__description";
        text.textContent = description;

        body.append(heading, text);
        card.appendChild(body);

        if (footer) {
            const footerEl = document.createElement("div");
            footerEl.className = "ui-card__footer";
            if (footer instanceof Node) {
                footerEl.appendChild(footer);
            } else {
                footerEl.textContent = footer;
            }
            card.appendChild(footerEl);
        }

        return card;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createCard = createCard;
})();
