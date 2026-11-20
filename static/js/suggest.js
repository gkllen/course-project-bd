/* Живые подсказки поиска: /api/suggest/?q=  (debounce 200 мс, клавиатурная навигация). */
(function () {
  "use strict";

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function attach(input) {
    var url = input.getAttribute("data-suggest");
    var wrap = input.parentElement;
    var box = document.createElement("ul");
    box.className = "suggest-box";
    box.setAttribute("role", "listbox");
    box.hidden = true;
    wrap.appendChild(box);
    input.setAttribute("autocomplete", "off");
    input.setAttribute("aria-autocomplete", "list");

    var timer = null, items = [], active = -1, lastQuery = "";

    function close() { box.hidden = true; active = -1; }

    function render() {
      if (!items.length) { close(); return; }
      box.innerHTML = items.map(function (s, i) {
        return '<li role="option" class="' + (i === active ? "active" : "") + '">' +
          '<a href="' + s.url + '">' +
          '<span class="badge" style="--c:' + s.color + '">' + escapeHtml(s.type) + '</span>' +
          '<span class="s-title">' + escapeHtml(s.title) + '</span>' +
          (s.year ? '<span class="s-year">' + s.year + '</span>' : '') +
          '</a></li>';
      }).join("");
      box.hidden = false;
    }

    function fetchSuggestions(q) {
      fetch(url + "?q=" + encodeURIComponent(q), { headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (input.value.trim() !== q) return;  // устаревший ответ
          items = data.suggestions || [];
          active = -1;
          render();
        })
        .catch(close);
    }

    input.addEventListener("input", function () {
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) { items = []; close(); return; }
      if (q === lastQuery && items.length) { render(); return; }
      lastQuery = q;
      timer = setTimeout(function () { fetchSuggestions(q); }, 200);
    });

    input.addEventListener("keydown", function (e) {
      if (box.hidden) return;
      if (e.key === "ArrowDown") { active = Math.min(active + 1, items.length - 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(active - 1, -1); render(); e.preventDefault(); }
      else if (e.key === "Escape") { close(); }
      else if (e.key === "Enter" && active >= 0) { window.location = items[active].url; e.preventDefault(); }
    });

    input.addEventListener("blur", function () { setTimeout(close, 150); });
    input.addEventListener("focus", function () { if (items.length) render(); });
  }

  document.querySelectorAll("input[data-suggest]").forEach(attach);
})();
