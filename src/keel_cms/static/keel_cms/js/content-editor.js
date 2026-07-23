/* Shared body editor for blog + news add/edit forms.

   Three editable views over one body (canonical = full HTML, carried in the
   hidden #id_content_html textarea):
     - HTML Preview : contenteditable render (default tab)
     - HTML         : CodeMirror (htmlmixed highlight, line numbers, tag matching,
                      active line, auto-close), pretty-printed via js-beautify
     - Markdown     : EasyMDE (its toolbar is disabled; one shared toolbar drives all tabs)

   Generated visual components (cp-*, mermaid, charts, scripts) are protected,
   deletable placeholder chips in Preview and Markdown (raw/editable in the HTML
   tab); they round-trip byte-stable and deleting a chip removes the component.

   Config comes from the #content-editor-config JSON script rendered by
   _content_editor.html. */
(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", init);

    function readConfig() {
        var el = document.getElementById("content-editor-config");
        if (!el) return {};
        try { return JSON.parse(el.textContent || "{}"); } catch (e) { return {}; }
    }

    function escapeAttr(s) { return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
    function escapeHtmlInner(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
    function setModal(name, value) {
        var root = document.querySelector("body");
        if (root && root._x_dataStack) root._x_dataStack[0][name] = value;
    }

    function init() {
        var cfg = readConfig();
        var csrfEl = document.querySelector("[name=csrfmiddlewaretoken]");
        var csrfToken = csrfEl ? csrfEl.value : "";

        wireTags();
        wireNowButton();
        wireFeaturedUpload(cfg, csrfToken);

        var mdTextarea = document.getElementById("id_content_markdown");
        var easymde = null;
        if (mdTextarea && typeof EasyMDE !== "undefined") {
            easymde = new EasyMDE({
                element: mdTextarea,
                spellChecker: false,
                status: false,
                toolbar: false,
                autoDownloadFontAwesome: false,
                minHeight: "500px",
                renderingConfig: { singleLineBreaks: false, codeSyntaxHighlighting: false },
            });
            window.__contentEditorEasyMde = easymde;
        }

        wireEditorShell(cfg, csrfToken, easymde);
    }

    /* ── Tags (glossary-term chips) ─────────────────────────────────────── */
    function wireTags() {
        var tagInput = document.getElementById("tag-input");
        var tagsContainer = document.getElementById("tags-container");
        var tagNamesInput = document.getElementById("tag-names-input");
        if (!tagInput || !tagsContainer || !tagNamesInput) return;

        function updateTagNames() {
            var names = Array.prototype.map.call(tagsContainer.querySelectorAll(".tag-chip"), function (c) { return c.dataset.name; });
            tagNamesInput.value = names.filter(Boolean).join(", ");
        }
        function addTagChip(name) {
            var span = document.createElement("span");
            span.className = "tag-chip inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300";
            span.dataset.name = name;
            span.innerHTML = "<span>" + escapeHtmlInner(name) + "</span><button type=\"button\" class=\"rm text-gray-400 hover:text-error-500\" aria-label=\"Remove\">&times;</button>";
            tagsContainer.appendChild(span);
            updateTagNames();
        }
        (tagNamesInput.value ? tagNamesInput.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean) : []).forEach(addTagChip);

        tagInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                var val = this.value.replace(/,/g, "").trim();
                if (val) { addTagChip(val); this.value = ""; }
            }
        });
        tagsContainer.addEventListener("click", function (e) {
            var btn = e.target.closest("button.rm");
            if (btn) { btn.closest(".tag-chip").remove(); updateTagNames(); }
        });
    }

    /* ── "Now" button for the publish date ──────────────────────────────── */
    function wireNowButton() {
        var btnNow = document.getElementById("btn-now");
        var dateInput = document.getElementById("id_published_at");
        if (!btnNow || !dateInput) return;
        btnNow.addEventListener("click", function () {
            var now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            dateInput.value = now.toISOString().slice(0, 16);
        });
    }

    /* ── Featured image upload zone ─────────────────────────────────────── */
    function wireFeaturedUpload(cfg, csrfToken) {
        var uploadZone = document.getElementById("upload-zone");
        var fileInput = document.getElementById("file-input");
        var previewImg = document.getElementById("preview-img");
        var uploadIcon = document.getElementById("upload-icon");
        var uploadText = document.getElementById("upload-text");
        var uploadHint = document.getElementById("upload-hint");
        var urlInput = document.getElementById("id_featured_image_url");
        if (!uploadZone || !fileInput || !urlInput) return;

        function showFeaturedPreview(url) {
            if (url) {
                previewImg.src = url; previewImg.style.display = "block";
                if (uploadIcon) uploadIcon.style.display = "none";
                if (uploadText) uploadText.style.display = "none";
                if (uploadHint) uploadHint.style.display = "none";
            } else {
                previewImg.src = ""; previewImg.style.display = "none";
                if (uploadIcon) uploadIcon.style.display = "";
                if (uploadText) uploadText.style.display = "";
                if (uploadHint) uploadHint.style.display = "";
            }
        }
        if (urlInput.value) showFeaturedPreview(urlInput.value);

        if (cfg.featuredGenerateUrl) {
            window.__postFormFeatured = { showPreview: showFeaturedPreview, csrfToken: csrfToken, urlInput: urlInput, generateUrl: cfg.featuredGenerateUrl };
        }

        urlInput.addEventListener("input", function () { showFeaturedPreview(urlInput.value); });
        urlInput.addEventListener("paste", function () { setTimeout(function () { showFeaturedPreview(urlInput.value); }, 0); });

        var currentBlobUrl = null;
        fileInput.addEventListener("change", function () {
            if (!(this.files && this.files[0])) return;
            if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
            currentBlobUrl = URL.createObjectURL(this.files[0]);
            showFeaturedPreview(currentBlobUrl);
            var fd = new FormData();
            fd.append("file", this.files[0]);
            fd.append("csrfmiddlewaretoken", csrfToken);
            if (cfg.section) fd.append("section", cfg.section);
            fetch(cfg.uploadUrl, { method: "POST", body: fd, headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (currentBlobUrl) { URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
                    if (data.error) { alert(data.error); showFeaturedPreview(urlInput.value); fileInput.value = ""; return; }
                    if (data.url) { urlInput.value = data.url; showFeaturedPreview(data.url); fileInput.value = ""; }
                })
                .catch(function () {
                    if (currentBlobUrl) { URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
                    showFeaturedPreview(urlInput.value); fileInput.value = "";
                });
        });

        uploadZone.addEventListener("dragover", function (e) { e.preventDefault(); uploadZone.classList.add("dragover"); });
        uploadZone.addEventListener("dragleave", function (e) { e.preventDefault(); uploadZone.classList.remove("dragover"); });
        uploadZone.addEventListener("drop", function (e) {
            e.preventDefault(); uploadZone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files[0]) { fileInput.files = e.dataTransfer.files; fileInput.dispatchEvent(new Event("change")); }
        });
    }

    /* ── Component protection ───────────────────────────────────────────── */
    var COMPONENT_SELECTOR = 'figure[class*="cp-"], div[class*="cp-"], [class*="mermaid"], [data-cp-chart], script';

    function outermostComponents(root) {
        var all = Array.prototype.slice.call(root.querySelectorAll(COMPONENT_SELECTOR));
        return all.filter(function (el) { return !all.some(function (o) { return o !== el && o.contains(el); }); });
    }
    function componentLabel(el) {
        var t = el.getAttribute("data-cp-title") || el.getAttribute("data-ce-label");
        if (t) return t.trim().slice(0, 60);
        var cap = el.querySelector ? el.querySelector("figcaption") : null;
        if (cap && cap.textContent.trim()) return cap.textContent.trim().slice(0, 60);
        var cls = el.getAttribute("class") || "";
        if (/mermaid/i.test(cls)) return "Diagram";
        if ((el.hasAttribute && el.hasAttribute("data-cp-chart")) || /chart/i.test(cls)) return "Chart";
        if ((el.tagName || "").toLowerCase() === "script") return "Script";
        var m = cls.match(/cp-([a-z0-9]+)/i);
        if (m) { var n = m[1].replace(/-/g, " "); return n.charAt(0).toUpperCase() + n.slice(1); }
        return "Component";
    }
    function chipMarkup(label) {
        return '<span class="ce-comp__icon" aria-hidden="true">&#9639;</span>' +
            '<span class="ce-comp__label">' + escapeHtmlInner(label) + '</span>' +
            '<span class="ce-comp__hint">component</span>' +
            '<button type="button" class="ce-comp__del" title="Remove component" aria-label="Remove component">&times;</button>';
    }

    var BEAUTIFY_OPTS = {
        indent_size: 2, wrap_line_length: 0, preserve_newlines: true, max_preserve_newlines: 1,
        indent_inner_html: true, unformatted: [], extra_liners: [],
        content_unformatted: ["pre", "textarea", "code", "script", "style", "svg", "math"],
    };
    function beautifyHtml(html) {
        try { return (typeof window.html_beautify === "function") ? window.html_beautify(html || "", BEAUTIFY_OPTS) : (html || ""); }
        catch (e) { return html || ""; }
    }

    /* ── Editor shell: tabs, toolbar, component sync, submit ─────────────── */
    function wireEditorShell(cfg, csrfToken, easymde) {
        var form = document.getElementById("post-form");
        var htmlTextarea = document.getElementById("id_content_html");
        var formatInput = document.getElementById("id_content_format");
        var preview = document.getElementById("ce-preview");
        if (!htmlTextarea || !formatInput || !preview) return;

        var tabs = Array.prototype.slice.call(document.querySelectorAll(".ce-tab"));
        var panes = Array.prototype.slice.call(document.querySelectorAll(".ce-pane"));
        var statusEl = document.getElementById("ce-convert-status");

        var activeTab = "preview";
        var dirty = false, everEdited = false, switching = false, suppressMd = false;
        var previewComponents = {}, mdComponents = {}, mdBuiltFrom = null, htmlBuiltFrom = null, savedSel = null;

        function getCanon() { return htmlTextarea.value; }
        function setCanon(v) { htmlTextarea.value = v; }
        function setFormat(f) { formatInput.value = f; }
        function markEdited() { dirty = true; everEdited = true; setFormat("html"); }
        function setStatus(msg, err) { if (!statusEl) return; statusEl.textContent = msg || ""; if (err) statusEl.setAttribute("data-state", "error"); else statusEl.removeAttribute("data-state"); }
        function setBusy(b) {
            if (!statusEl) return;
            if (b) { statusEl.textContent = "Syncing…"; statusEl.setAttribute("data-state", "busy"); }
            else if (statusEl.getAttribute("data-state") === "busy") { statusEl.textContent = ""; statusEl.removeAttribute("data-state"); }
        }
        function mdValue() { return easymde ? easymde.value() : ""; }
        function setMdValue(v) { suppressMd = true; if (easymde) easymde.value(v); suppressMd = false; }

        /* HTML tab: real code editor when CodeMirror is available. */
        var htmlCM = null;
        var htmlHost = document.getElementById("ce-html-cm");
        if (htmlHost && typeof CodeMirror !== "undefined") {
            htmlCM = CodeMirror(htmlHost, {
                value: getCanon(),
                mode: "htmlmixed",
                lineNumbers: true,
                lineWrapping: true,
                matchTags: { bothTags: true },
                autoCloseTags: true,
                styleActiveLine: true,
                indentUnit: 2,
                tabSize: 2,
            });
            htmlTextarea.style.display = "none";
            htmlCM.on("change", function () { markEdited(); });
        } else {
            htmlTextarea.addEventListener("input", markEdited);
        }

        function apiConvert(payload) {
            return fetch(cfg.convertUrl, {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken },
                body: JSON.stringify(payload),
            }).then(function (r) {
                return r.text().then(function (t) {
                    var d = {};
                    if (t) { try { d = JSON.parse(t); } catch (e) { d = { error: t.trim().slice(0, 200) || r.statusText }; } }
                    if (!r.ok || (d && d.error)) { throw new Error((d && d.error) || ("HTTP " + r.status)); }
                    return d;
                });
            });
        }

        /* Preview: components -> chips; serialize chips -> component HTML */
        function buildPreview(fullHtml) {
            var doc = new DOMParser().parseFromString('<div id="ce-root">' + (fullHtml || "") + "</div>", "text/html");
            var root = doc.getElementById("ce-root");
            previewComponents = {};
            outermostComponents(root).forEach(function (el, i) {
                var cid = "p" + i;
                previewComponents[cid] = el.outerHTML;
                var chip = doc.createElement("div");
                chip.className = "ce-comp"; chip.setAttribute("contenteditable", "false"); chip.setAttribute("data-cid", cid);
                chip.innerHTML = chipMarkup(componentLabel(el));
                el.parentNode.replaceChild(chip, el);
            });
            preview.innerHTML = root.innerHTML;
        }
        function serializePreview() {
            var clone = preview.cloneNode(true);
            Array.prototype.slice.call(clone.querySelectorAll(".ce-comp[data-cid]")).forEach(function (chip) {
                var cid = chip.getAttribute("data-cid"), html = previewComponents[cid];
                if (html != null) {
                    var tmp = document.createElement("div"); tmp.innerHTML = html;
                    var frag = document.createDocumentFragment();
                    while (tmp.firstChild) frag.appendChild(tmp.firstChild);
                    chip.parentNode.replaceChild(frag, chip);
                } else {
                    chip.parentNode.removeChild(chip);
                }
            });
            setCanon(clone.innerHTML);
        }

        /* Markdown: mask components -> tokens, html2md, decorate as widgets */
        function buildMarkdown(fullHtml) {
            var doc = new DOMParser().parseFromString('<div id="ce-root">' + (fullHtml || "") + "</div>", "text/html");
            var root = doc.getElementById("ce-root");
            mdComponents = {}; var items = [];
            outermostComponents(root).forEach(function (el, i) {
                var token = "CECMP" + i + "ENDCMP", label = componentLabel(el);
                mdComponents[token] = { label: label, html: el.outerHTML };
                items.push({ token: token, label: label });
                el.parentNode.replaceChild(doc.createTextNode("\n\n" + token + "\n\n"), el);
            });
            return apiConvert({ direction: "html2md", html: root.innerHTML, section: cfg.section }).then(function (data) {
                setMdValue(data.markdown || "");
                decorateMdTokens(items);
            });
        }
        function decorateMdTokens(items) {
            if (!easymde) return;
            var cm = easymde.codemirror, doc = cm.getValue();
            items.forEach(function (item) {
                var idx = doc.indexOf(item.token);
                if (idx < 0) return;
                var from = cm.posFromIndex(idx), to = cm.posFromIndex(idx + item.token.length);
                var el = document.createElement("span");
                el.className = "ce-comp ce-comp--md"; el.setAttribute("contenteditable", "false");
                el.innerHTML = chipMarkup(item.label);
                var mark = cm.markText(from, to, { atomic: true, replacedWith: el, clearWhenEmpty: true });
                el.querySelector(".ce-comp__del").addEventListener("click", function (ev) {
                    ev.preventDefault();
                    var pos = mark.find();
                    if (pos) cm.replaceRange("", pos.from, pos.to);
                    markEdited();
                });
            });
        }
        function serializeMarkdown() {
            return apiConvert({ direction: "md2html", markdown: mdValue(), is_pipeline: !!cfg.isPipeline, section: cfg.section }).then(function (data) {
                var html = data.html || "";
                Object.keys(mdComponents).forEach(function (token) {
                    var comp = mdComponents[token];
                    html = html.split("<p>" + token + "</p>").join(comp.html).split(token).join(comp.html);
                });
                setCanon(html);
            });
        }

        function flushActive() {
            if (!dirty) return Promise.resolve();
            if (activeTab === "preview") { serializePreview(); dirty = false; return Promise.resolve(); }
            if (activeTab === "markdown") { return serializeMarkdown().then(function () { dirty = false; }); }
            if (activeTab === "html") { if (htmlCM) { setCanon(htmlCM.getValue()); htmlBuiltFrom = getCanon(); } dirty = false; return Promise.resolve(); }
            dirty = false; return Promise.resolve();
        }
        function buildTab(target) {
            if (target === "preview") { buildPreview(getCanon()); return Promise.resolve(); }
            if (target === "markdown") {
                if (mdBuiltFrom === getCanon() && easymde) return Promise.resolve();
                return buildMarkdown(getCanon()).then(function () { mdBuiltFrom = getCanon(); });
            }
            if (target === "html") {
                if (htmlCM && htmlBuiltFrom !== getCanon()) { htmlCM.setValue(beautifyHtml(getCanon())); htmlBuiltFrom = getCanon(); }
                return Promise.resolve();
            }
            return Promise.resolve();
        }
        function showTab(name) {
            activeTab = name;
            panes.forEach(function (p) { p.hidden = p.getAttribute("data-ce-pane") !== name; });
            tabs.forEach(function (t) { t.classList.toggle("ce-tab--active", t.getAttribute("data-ce-tab") === name); });
            if (name === "markdown" && easymde) { easymde.codemirror.refresh(); setTimeout(function () { easymde.codemirror.refresh(); }, 0); }
            if (name === "html" && htmlCM) { htmlCM.refresh(); setTimeout(function () { htmlCM.refresh(); }, 0); }
        }
        function activateTab(target) {
            if (switching || target === activeTab) return;
            switching = true; setBusy(true);
            flushActive().then(function () { return buildTab(target); }).then(function () {
                showTab(target); setBusy(false); switching = false;
            }).catch(function (err) {
                setBusy(false); switching = false;
                setStatus("Sync failed: " + (err && err.message ? err.message : "error") + " — staying on this tab.", true);
            });
        }

        tabs.forEach(function (t) { t.addEventListener("click", function () { activateTab(t.getAttribute("data-ce-tab")); }); });

        /* Edit tracking */
        if (easymde) easymde.codemirror.on("change", function () { if (!suppressMd) markEdited(); });
        preview.addEventListener("input", markEdited);
        preview.addEventListener("click", function (e) {
            var del = e.target.closest(".ce-comp__del");
            if (!del) return;
            e.preventDefault();
            var chip = del.closest(".ce-comp");
            if (chip) { chip.parentNode.removeChild(chip); markEdited(); }
        });

        /* ── Toolbar (acts on the active surface) ───────────────────────── */
        function activeCM() { return activeTab === "markdown" ? (easymde && easymde.codemirror) : (activeTab === "html" ? htmlCM : null); }
        function cmWrapSel(cm, before, after) { cm.replaceSelection(before + cm.getSelection() + after); cm.focus(); }
        function cmInsertBlk(cm, html, blank) {
            var cur = cm.getCursor(), sep = blank ? "\n\n" : "\n";
            var pre = cm.getLine(cur.line).length > 0 ? sep : "";
            cm.replaceRange(pre + html + sep, cur); cm.focus();
        }
        function taWrap(before, after, block) {
            var ta = htmlTextarea, s = ta.selectionStart, e = ta.selectionEnd, sel = ta.value.slice(s, e);
            var ins = before + sel + after; if (block) ins = "\n" + ins + "\n";
            ta.value = ta.value.slice(0, s) + ins + ta.value.slice(e);
            var caret = s + before.length + (block ? 1 : 0);
            ta.focus(); ta.setSelectionRange(caret, caret + sel.length); markEdited();
        }

        function snapshotSelection() {
            if (activeTab === "preview") {
                var s = window.getSelection();
                savedSel = (s && s.rangeCount && preview.contains(s.anchorNode)) ? s.getRangeAt(0).cloneRange() : null;
            } else { savedSel = null; }
        }
        function selectedText() {
            var cm = activeCM();
            if (cm) return cm.getSelection();
            if (activeTab === "html") return htmlTextarea.value.substring(htmlTextarea.selectionStart, htmlTextarea.selectionEnd);
            if (activeTab === "preview") { var s = window.getSelection(); return s ? s.toString() : ""; }
            return "";
        }
        function insertHtmlActive(html, block) {
            markEdited();
            var cm = activeCM();
            if (cm) { if (block) cmInsertBlk(cm, html, activeTab === "markdown"); else { cm.replaceSelection(html); cm.focus(); } return; }
            if (activeTab === "html") {
                var s = htmlTextarea.selectionStart, e = htmlTextarea.selectionEnd, ins = block ? ("\n" + html + "\n") : html;
                htmlTextarea.value = htmlTextarea.value.slice(0, s) + ins + htmlTextarea.value.slice(e);
                var pos = s + ins.length; htmlTextarea.focus(); htmlTextarea.setSelectionRange(pos, pos);
                return;
            }
            if (activeTab === "preview") {
                preview.focus();
                if (savedSel && savedSel.cloneRange) { var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(savedSel); }
                document.execCommand("insertHTML", false, html);
            }
        }

        var MD_FORMAT_METHODS = {
            bold: "toggleBold", italic: "toggleItalic", h2: "toggleHeading2", h3: "toggleHeading3",
            quote: "toggleBlockquote", ul: "toggleUnorderedList", ol: "toggleOrderedList",
        };
        var HTML_WRAP = {
            bold: ["<strong>", "</strong>", false], italic: ["<em>", "</em>", false],
            h2: ["<h2>", "</h2>", true], h3: ["<h3>", "</h3>", true], quote: ["<blockquote>", "</blockquote>", true],
        };
        function applyFormat(cmd) {
            markEdited();
            if (activeTab === "markdown" && easymde) {
                var method = MD_FORMAT_METHODS[cmd];
                if (method && typeof easymde[method] === "function") easymde[method]();
                return;
            }
            if (activeTab === "html") {
                if (cmd === "ul") { insertHtmlActive("<ul>\n  <li></li>\n</ul>", true); return; }
                if (cmd === "ol") { insertHtmlActive("<ol>\n  <li></li>\n</ol>", true); return; }
                var w = HTML_WRAP[cmd]; if (!w) return;
                if (htmlCM) cmWrapSel(htmlCM, w[0], w[1]); else taWrap(w[0], w[1], w[2]);
                return;
            }
            if (activeTab === "preview") {
                switch (cmd) {
                    case "bold": document.execCommand("bold"); break;
                    case "italic": document.execCommand("italic"); break;
                    case "h2": document.execCommand("formatBlock", false, "h2"); break;
                    case "h3": document.execCommand("formatBlock", false, "h3"); break;
                    case "quote": document.execCommand("formatBlock", false, "blockquote"); break;
                    case "ul": document.execCommand("insertUnorderedList"); break;
                    case "ol": document.execCommand("insertOrderedList"); break;
                }
            }
        }
        function openToolModal(cmd) {
            if (cmd === "link") {
                document.getElementById("link-anchor-text").value = selectedText() || "";
                document.getElementById("link-url").value = "";
                document.getElementById("link-new-tab").checked = true;
                ["link-nofollow", "link-sponsored", "link-ugc", "link-rel-noopener", "link-rel-noreferrer"].forEach(function (id) { document.getElementById(id).checked = false; });
                setModal("isModalLink", true);
                setTimeout(function () { document.getElementById("link-url").focus(); }, 80);
            } else if (cmd === "image") {
                document.getElementById("content-image-input").value = "";
                document.getElementById("content-image-caption").value = "";
                setModal("isModalImage", true);
            } else if (cmd === "ai") {
                window.__aiInlineImageUrl = "";
                document.getElementById("ai-inline-image-prompt").value = "";
                document.getElementById("ai-inline-image-caption").value = "";
                document.getElementById("ai-inline-image-status").textContent = "";
                var wrap = document.getElementById("ai-inline-image-preview-wrap"), prev = document.getElementById("ai-inline-image-preview");
                if (wrap) wrap.hidden = true; if (prev) prev.removeAttribute("src");
                var ins = document.getElementById("btn-ai-inline-image-insert"); if (ins) ins.disabled = true;
                setModal("isModalAi", true);
                setTimeout(function () { document.getElementById("ai-inline-image-prompt").focus(); }, 80);
            } else if (cmd === "read") {
                document.getElementById("read-resource-url").value = "";
                document.getElementById("read-resource-title").value = "";
                setModal("isModalRead", true);
            }
        }
        var tools = document.getElementById("ce-tools");
        if (tools) Array.prototype.slice.call(tools.querySelectorAll(".ce-tool")).forEach(function (b) {
            b.addEventListener("mousedown", function (e) { e.preventDefault(); });
            b.addEventListener("click", function () {
                var cmd = b.getAttribute("data-ce-cmd");
                if (cmd === "link" || cmd === "image" || cmd === "ai" || cmd === "read") { snapshotSelection(); openToolModal(cmd); }
                else applyFormat(cmd);
            });
        });

        /* Modal "Insert" buttons -> insert into the active surface */
        var btnLink = document.getElementById("btn-insert-link");
        if (btnLink) btnLink.addEventListener("click", function () {
            var href = document.getElementById("link-url").value.trim();
            if (!href) { alert("Please enter a URL."); return; }
            var raw = document.getElementById("link-anchor-text").value, text = raw.trim() !== "" ? raw : href;
            var newTab = document.getElementById("link-new-tab").checked, rel = [];
            if (document.getElementById("link-nofollow").checked) rel.push("nofollow");
            if (document.getElementById("link-sponsored").checked) rel.push("sponsored");
            if (document.getElementById("link-ugc").checked) rel.push("ugc");
            if (document.getElementById("link-rel-noopener").checked) rel.push("noopener");
            if (document.getElementById("link-rel-noreferrer").checked) rel.push("noreferrer");
            var attrs = 'href="' + escapeAttr(href) + '"';
            if (newTab) attrs += ' target="_blank"';
            if (rel.length) attrs += ' rel="' + escapeAttr(Array.from(new Set(rel)).join(" ")) + '"';
            insertHtmlActive("<a " + attrs + ">" + escapeHtmlInner(text) + "</a>", false);
            setModal("isModalLink", false);
        });

        var btnFigure = document.getElementById("btn-insert-figure");
        if (btnFigure) btnFigure.addEventListener("click", function () {
            var caption = document.getElementById("content-image-caption").value.trim();
            var file = document.getElementById("content-image-input").files[0];
            if (!file) { alert("Please select an image file first."); return; }
            var fd = new FormData(); fd.append("file", file); fd.append("csrfmiddlewaretoken", csrfToken);
            if (cfg.section) fd.append("section", cfg.section);
            fetch(cfg.uploadUrl, { method: "POST", body: fd, headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.error) { alert(data.error); return; }
                    if (!data.url) return;
                    var fig = caption
                        ? '<figure><img src="' + escapeAttr(data.url) + '" alt="' + escapeAttr(caption) + '"><figcaption>' + escapeHtmlInner(caption) + "</figcaption></figure>"
                        : '<figure><img src="' + escapeAttr(data.url) + '" alt=""></figure>';
                    insertHtmlActive(fig, true);
                    setModal("isModalImage", false);
                })
                .catch(function () {});
        });

        var btnRead = document.getElementById("btn-insert-read");
        if (btnRead) btnRead.addEventListener("click", function () {
            var url = document.getElementById("read-resource-url").value.trim() || "#";
            var title = document.getElementById("read-resource-title").value.trim() || "Link text";
            insertHtmlActive('<div class="in-content-read"><i class="fa-solid fa-bolt"></i><div class="in-content-read-text"><div class="in-content-read-label">Recommended Reading</div><a href="' + escapeAttr(url) + '">' + escapeHtmlInner(title) + "</a></div></div>", true);
            setModal("isModalRead", false);
        });

        if (cfg.aiInlineUrl) wireAiInlineImage(cfg, csrfToken, insertHtmlActive);

        /* ── Save: keep canonical HTML current; handle async Markdown ────── */
        var actionButtons = Array.prototype.slice.call(document.querySelectorAll('[form="post-form"][name="action"]'));
        actionButtons.forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                if (activeTab === "markdown" && dirty) {
                    e.preventDefault(); setBusy(true);
                    serializeMarkdown().then(function () {
                        dirty = false; if (everEdited) setFormat("html"); setBusy(false);
                        if (form.requestSubmit) form.requestSubmit(btn); else form.submit();
                    }).catch(function (err) {
                        setBusy(false); setStatus("Could not sync Markdown before saving: " + (err && err.message ? err.message : "error"), true);
                    });
                }
            });
        });
        if (form) form.addEventListener("submit", function () {
            if (activeTab === "preview" && dirty) { serializePreview(); dirty = false; }
            if (activeTab === "html" && htmlCM) setCanon(htmlCM.getValue());
            if (everEdited) setFormat("html");
        });

        /* Default view is the HTML Preview. */
        buildPreview(getCanon());
        showTab("preview");
    }

    function wireAiInlineImage(cfg, csrfToken, insertHtmlActive) {
        var btnGen = document.getElementById("btn-ai-inline-image-generate");
        var btnIns = document.getElementById("btn-ai-inline-image-insert");
        if (btnGen) btnGen.addEventListener("click", function () {
            var ta = document.getElementById("ai-inline-image-prompt");
            var st = document.getElementById("ai-inline-image-status");
            var wrap = document.getElementById("ai-inline-image-preview-wrap");
            var prev = document.getElementById("ai-inline-image-preview");
            var prompt = (ta && ta.value ? ta.value : "").trim();
            if (!prompt) { if (st) st.textContent = "Enter a prompt first."; return; }
            btnGen.disabled = true;
            if (st) st.textContent = "Generating…";
            fetch(cfg.aiInlineUrl, {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ prompt: prompt }),
            })
                .then(function (r) { return r.text().then(function (text) { var data = {}; if (text) { try { data = JSON.parse(text); } catch (e) { data = { error: text.trim().slice(0, 200) || r.statusText || "Bad response" }; } } return { ok: r.ok, status: r.status, data: data }; }); })
                .then(function (res) {
                    if (res.status === 404) { if (st) st.textContent = "Route not found (404)."; return; }
                    if (!res.ok || (res.data && res.data.error)) {
                        var msg = (res.data && res.data.error) || "Request failed.";
                        if (res.status >= 400) msg += " (HTTP " + res.status + ")";
                        if (st) st.textContent = msg; return;
                    }
                    if (res.data && res.data.url) {
                        window.__aiInlineImageUrl = res.data.url;
                        if (prev) { prev.src = res.data.url; prev.alt = "Generated preview"; }
                        if (wrap) wrap.hidden = false;
                        if (btnIns) btnIns.disabled = false;
                        if (st) st.textContent = "Done. Preview above — adjust caption if needed, then Insert.";
                    }
                })
                .catch(function () { if (st) st.textContent = "Network error."; })
                .finally(function () { btnGen.disabled = false; });
        });
        if (btnIns) btnIns.addEventListener("click", function () {
            var url = window.__aiInlineImageUrl; if (!url) return;
            var capEl = document.getElementById("ai-inline-image-caption");
            var caption = capEl && capEl.value ? capEl.value.trim() : "";
            var fig = caption
                ? '<figure><img src="' + escapeAttr(url) + '" alt="' + escapeAttr(caption) + '"><figcaption>' + escapeHtmlInner(caption) + "</figcaption></figure>"
                : '<figure><img src="' + escapeAttr(url) + '" alt=""></figure>';
            insertHtmlActive(fig, true);
            setModal("isModalAi", false);
        });
    }
})();
