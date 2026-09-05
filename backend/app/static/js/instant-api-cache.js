(function () {
    const originalFetch = window.fetch.bind(window);
    const userScope = document.body?.dataset.cacheUser || "guest";
    const storagePrefix = `instant-api-cache:v1:${userScope}:`;

    function requestInfo(input, init = {}) {
        const requestUrl = input instanceof Request ? input.url : input;
        const url = new URL(requestUrl, window.location.origin);
        const method = (init.method || (input instanceof Request ? input.method : "GET") || "GET").toUpperCase();
        return { url, method };
    }

    function canCache(url, method) {
        return method === "GET"
            && url.origin === window.location.origin
            && url.pathname.startsWith("/api/")
            && !url.pathname.startsWith("/api/auth/");
    }

    function cacheKey(url) {
        return `${storagePrefix}${url.pathname}${url.search}`;
    }

    function clearApiCache() {
        try {
            Object.keys(sessionStorage)
                .filter((key) => key.startsWith(storagePrefix))
                .forEach((key) => sessionStorage.removeItem(key));
        } catch (_) {}
    }

    function storeResponse(key, response) {
        if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) return;
        response.clone().text().then((body) => {
            try {
                sessionStorage.setItem(key, JSON.stringify({
                    body,
                    status: response.status,
                    statusText: response.statusText,
                    contentType: response.headers.get("content-type"),
                }));
            } catch (_) {}
        }).catch(() => {});
    }

    function cachedResponse(cached) {
        return new Response(cached.body, {
            status: cached.status || 200,
            statusText: cached.statusText || "OK",
            headers: { "content-type": cached.contentType || "application/json" },
        });
    }

    window.fetch = function (input, init = {}) {
        const { url, method } = requestInfo(input, init);
        if (!canCache(url, method)) {
            return originalFetch(input, init).then((response) => {
                if (method !== "GET" && url.origin === window.location.origin && url.pathname.startsWith("/api/")) {
                    clearApiCache();
                }
                return response;
            });
        }

        const key = cacheKey(url);
        try {
            const cached = JSON.parse(sessionStorage.getItem(key) || "null");
            if (cached?.body) {
                // Render the previous result immediately, then refresh it for the next view.
                originalFetch(input, init).then((response) => storeResponse(key, response)).catch(() => {});
                return Promise.resolve(cachedResponse(cached));
            }
        } catch (_) {}

        return originalFetch(input, init).then((response) => {
            storeResponse(key, response);
            return response;
        });
    };
})();
