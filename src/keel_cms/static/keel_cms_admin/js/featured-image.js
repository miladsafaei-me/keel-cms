/* Wire the blog post editor's "AI featured image" button. keel-web's
   content-editor.js publishes window.__postFormFeatured { showPreview, csrfToken,
   urlInput, generateUrl } as the seam for the host to add this control; this reads
   it at click time so script load order does not matter. */
(function () {
    document.addEventListener("DOMContentLoaded", function () {
        var btn = document.getElementById("post-form-ai-featured-generate");
        var promptEl = document.getElementById("post-form-ai-featured-prompt");
        var statusEl = document.getElementById("post-form-ai-featured-status");
        if (!btn || !promptEl) return;

        btn.addEventListener("click", function () {
            var cfg = window.__postFormFeatured;
            if (!cfg || !cfg.generateUrl) {
                if (statusEl) statusEl.textContent = "Image generation is not configured.";
                return;
            }
            var prompt = (promptEl.value || "").trim();
            if (!prompt) {
                if (statusEl) statusEl.textContent = "Enter a prompt first.";
                return;
            }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "Generating…";
            fetch(cfg.generateUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": cfg.csrfToken,
                },
                body: JSON.stringify({ prompt: prompt }),
            })
                .then(function (r) {
                    return r.text().then(function (t) {
                        var d = {};
                        if (t) {
                            try { d = JSON.parse(t); } catch (e) { d = { error: (t || "").slice(0, 200) }; }
                        }
                        return { ok: r.ok, status: r.status, data: d };
                    });
                })
                .then(function (res) {
                    if (!res.ok || (res.data && res.data.error)) {
                        var msg = (res.data && res.data.error) || "Request failed.";
                        if (res.status >= 400) msg += " (HTTP " + res.status + ")";
                        if (statusEl) statusEl.textContent = msg;
                        return;
                    }
                    if (res.data && res.data.url) {
                        if (cfg.urlInput) cfg.urlInput.value = res.data.url;
                        if (cfg.showPreview) cfg.showPreview(res.data.url);
                        if (statusEl) statusEl.textContent = "Done. Featured image set.";
                    }
                })
                .catch(function () { if (statusEl) statusEl.textContent = "Network error."; })
                .finally(function () { btn.disabled = false; });
        });
    });
})();
