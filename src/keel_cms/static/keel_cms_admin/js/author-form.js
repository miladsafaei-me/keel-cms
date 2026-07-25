/* Author editor: slug auto-generation, dynamic custom-social rows, and avatar
   upload. The avatar POSTs to the URL on #avatar-zone[data-upload-url] (the generic
   keel_cms_admin image-upload endpoint) and stores the returned URL in #id_avatar_url. */
(function () {
    document.addEventListener("DOMContentLoaded", function () {
        var csrfEl = document.querySelector("[name=csrfmiddlewaretoken]");
        var csrfToken = csrfEl ? csrfEl.value : "";

        var nameInput = document.getElementById("id_name");
        var slugInput = document.getElementById("id_slug");
        if (nameInput && slugInput) {
            var autofill = !slugInput.value.trim();
            slugInput.addEventListener("input", function () { autofill = false; });
            nameInput.addEventListener("input", function () {
                if (!autofill) return;
                slugInput.value = this.value
                    .toLowerCase().trim()
                    .replace(/[^\w\s-]/g, "")
                    .replace(/[\s_-]+/g, "-")
                    .replace(/^-+|-+$/g, "");
            });
        }

        var btnAddSocial = document.getElementById("btn-add-social");
        var container = document.getElementById("custom-socials-container");
        var customInput = document.getElementById("custom-socials-input");

        function safe(s) {
            return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
        }
        function updateCustom() {
            if (!customInput) return;
            var data = Array.prototype.map.call(container.querySelectorAll(".custom-social-row"), function (row) {
                var inputs = row.querySelectorAll("input");
                return { platform: inputs[0].value, url: inputs[1].value };
            }).filter(function (x) { return x.platform || x.url; });
            customInput.value = JSON.stringify(data);
        }
        function makeRow(platform, url) {
            var row = document.createElement("div");
            row.className = "flex items-center gap-2 custom-social-row";
            row.innerHTML =
                '<input type="text" class="ta-input flex-1" placeholder="Platform (e.g. Medium)" value="' + safe(platform) + '">' +
                '<input type="url" class="ta-input flex-[2]" placeholder="https://..." value="' + safe(url) + '">' +
                '<button type="button" title="Remove link" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gray-300 bg-white text-error-500 hover:bg-error-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-error-500/10">' +
                '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 7l16 0"/><path d="M10 11l0 6"/><path d="M14 11l0 6"/><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"/><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"/></svg>' +
                "</button>";
            row.querySelector("button").addEventListener("click", function () { row.remove(); updateCustom(); });
            Array.prototype.forEach.call(row.querySelectorAll("input"), function (i) { i.addEventListener("change", updateCustom); });
            return row;
        }
        if (btnAddSocial && container) {
            btnAddSocial.addEventListener("click", function () { container.appendChild(makeRow("", "")); updateCustom(); });
            if (customInput) {
                try {
                    (JSON.parse(customInput.value || "[]") || []).forEach(function (item) {
                        container.appendChild(makeRow(item.platform, item.url));
                    });
                } catch (e) { /* ignore malformed initial value */ }
            }
        }

        var zone = document.getElementById("avatar-zone");
        var input = document.getElementById("avatar-input");
        var preview = document.getElementById("avatar-preview");
        var icon = document.getElementById("avatar-icon");
        var text = document.getElementById("avatar-text");
        var btnRemove = document.getElementById("btn-remove-avatar");
        var urlInput = document.getElementById("id_avatar_url");
        var uploadUrl = zone ? zone.getAttribute("data-upload-url") : "";

        function showPreview(url) {
            if (!preview) return;
            if (url) {
                preview.src = url; preview.style.display = "block"; preview.classList.remove("hidden");
                if (icon) icon.style.display = "none";
                if (text) text.style.display = "none";
                if (btnRemove) { btnRemove.style.display = "inline-flex"; btnRemove.classList.remove("hidden"); }
            } else {
                preview.src = ""; preview.style.display = "none";
                if (icon) icon.style.display = "";
                if (text) text.style.display = "";
                if (btnRemove) btnRemove.style.display = "none";
            }
        }
        if (urlInput && urlInput.value) showPreview(urlInput.value);
        if (urlInput) {
            urlInput.addEventListener("input", function () { showPreview(urlInput.value); });
            urlInput.addEventListener("paste", function () { setTimeout(function () { showPreview(urlInput.value); }, 0); });
        }

        var blobUrl = null;
        if (input) {
            input.addEventListener("change", function () {
                if (!(this.files && this.files[0])) return;
                if (blobUrl) URL.revokeObjectURL(blobUrl);
                blobUrl = URL.createObjectURL(this.files[0]);
                showPreview(blobUrl);
                if (!uploadUrl) return;
                var fd = new FormData();
                fd.append("file", this.files[0]);
                fd.append("csrfmiddlewaretoken", csrfToken);
                fetch(uploadUrl, { method: "POST", body: fd, headers: { "X-Requested-With": "XMLHttpRequest" } })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
                        if (data.url && urlInput) { urlInput.value = data.url; showPreview(data.url); }
                    })
                    .catch(function () { if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; } });
            });
        }
        if (btnRemove) {
            btnRemove.addEventListener("click", function () {
                if (input) input.value = "";
                if (urlInput) urlInput.value = "";
                if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
                showPreview("");
            });
        }
    });
})();
