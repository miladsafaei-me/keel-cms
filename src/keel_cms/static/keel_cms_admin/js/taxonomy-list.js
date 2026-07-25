/* Topic / tag list pages: auto-fill the slug from the name (create only) and
   client-side filter the table rows. Both list templates use #id_name / #id_slug,
   #taxonomy-search and a #taxonomy-tbody whose rows carry data-name / data-slug. */
(function () {
    document.addEventListener("DOMContentLoaded", function () {
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

        var search = document.getElementById("taxonomy-search");
        var tbody = document.getElementById("taxonomy-tbody");
        if (search && tbody) {
            search.addEventListener("input", function () {
                var q = this.value.toLowerCase().trim();
                Array.prototype.forEach.call(tbody.querySelectorAll("tr"), function (row) {
                    if (!row.dataset || row.dataset.name === undefined) return;
                    var name = row.dataset.name || "";
                    var slug = row.dataset.slug || "";
                    row.style.display = (!q || name.indexOf(q) !== -1 || slug.indexOf(q) !== -1) ? "" : "none";
                });
            });
        }
    });
})();
