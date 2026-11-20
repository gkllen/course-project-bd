/* Мелкие сценарии страниц: автоприменение фасетов, оглавление, копирование цитаты. */
(function () {
  "use strict";

  // --- Каталог: применять фильтры сразу при изменении чекбокса / сортировки ---
  document.querySelectorAll("form[data-autosubmit]").forEach(function (form) {
    form.addEventListener("change", function (e) {
      if (e.target.matches("input[type=checkbox], select")) {
        var page = form.querySelector("input[name=page]");
        if (page) page.remove();
        form.submit();
      }
    });
  });

  // --- Страница записи: подсветка текущего раздела в оглавлении ---
  var tocLinks = document.querySelectorAll(".toc a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var map = {};
    tocLinks.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a.parentElement; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          tocLinks.forEach(function (a) { a.parentElement.classList.remove("active"); });
          var li = map[entry.target.id];
          if (li) li.classList.add("active");
        }
      });
    }, { rootMargin: "0px 0px -70% 0px" });
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }

  // --- Копирование библиографической ссылки ---
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = document.querySelector(btn.getAttribute("data-copy"));
      if (!target || !navigator.clipboard) return;
      navigator.clipboard.writeText(target.innerText.trim()).then(function () {
        var old = btn.textContent;
        btn.textContent = "Скопировано ✓";
        setTimeout(function () { btn.textContent = old; }, 1500);
      });
    });
  });
})();
