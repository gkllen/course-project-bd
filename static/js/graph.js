/*
 * Визуализация графа знаний на Cytoscape.js.
 * KBGraph.mount(element, options)
 *   options.url        — адрес /api/graph/ (с параметрами)
 *   options.info       — элемент панели справки (необязательно)
 *   options.typeInputs — чекбоксы фильтра по типам (необязательно)
 *   options.search     — поле поиска узла (необязательно)
 *   options.mini       — компактный режим для страницы записи
 */
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function styles(mini) {
    return [
      { selector: "node", style: {
          "background-color": "data(color)",
          "label": "data(label)",
          "width": "mapData(degree, 0, 60, " + (mini ? "14, 34" : "16, 64") + ")",
          "height": "mapData(degree, 0, 60, " + (mini ? "14, 34" : "16, 64") + ")",
          "font-size": mini ? 9 : "mapData(degree, 0, 40, 9, 15)",
          "font-family": "Segoe UI, Arial, sans-serif",
          "color": "#222",
          "text-valign": "bottom",
          "text-margin-y": 3,
          "text-wrap": "ellipsis",
          "text-max-width": mini ? 90 : 120,
          "text-background-color": "#fff",
          "text-background-opacity": 0.75,
          "text-background-padding": 1,
          "border-width": 1,
          "border-color": "#fff",
          "min-zoomed-font-size": mini ? 6 : 8
      }},
      { selector: "node[?focus]", style: { "border-width": 4, "border-color": "#f0b400" } },
      { selector: "edge", style: {
          "width": 1.2,
          "line-color": "#c3cbd1",
          "target-arrow-color": "#c3cbd1",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.7,
          "curve-style": "bezier",
          "opacity": 0.8
      }},
      { selector: "edge.show-label, edge:selected", style: {
          "label": "data(label)", "font-size": 8, "color": "#025e8d",
          "text-rotation": "autorotate", "text-background-color": "#fff",
          "text-background-opacity": 0.9, "text-background-padding": 1
      }},
      { selector: ".faded", style: { "opacity": 0.12, "text-opacity": 0 } },
      { selector: "node.hl", style: { "border-width": 3, "border-color": "#01324b" } },
      { selector: "edge.hl", style: { "line-color": "#025e8d", "target-arrow-color": "#025e8d", "width": 2, "opacity": 1 } },
      { selector: "node:selected", style: { "border-width": 4, "border-color": "#01324b" } }
    ];
  }

  function renderInfo(panel, node) {
    var d = node.data();
    var rels = [];
    node.connectedEdges().forEach(function (e) {
      var out = e.source().id() === node.id();
      var other = out ? e.target() : e.source();
      rels.push({
        label: out ? e.data("label") : e.data("inverse"),
        title: other.data("label"), url: other.data("url"), color: other.data("color"),
        note: e.data("note")
      });
    });
    rels.sort(function (a, b) { return a.label.localeCompare(b.label, "ru"); });
    panel.innerHTML =
      '<div class="node-card">' +
      '<span class="badge" style="--c:' + d.color + '">' + esc(d.type_name) + '</span>' +
      '<h3>' + esc(d.label) + '</h3>' +
      (d.year ? '<div class="muted small">' + d.year + '</div>' : '') +
      '<p>' + esc(d.summary) + '</p>' +
      '<p><a class="btn btn-sm" href="' + d.url + '">Открыть карточку</a> ' +
      '<a class="btn btn-sm btn-outline" href="/graph/?focus=' + encodeURIComponent(d.slug) + '">Окрестность узла</a></p>' +
      '<h2>Связи (' + rels.length + ')</h2>' +
      '<ul class="rels">' + rels.map(function (r) {
        return '<li><span class="swatch" style="--c:' + r.color + '"></span> <span class="lbl">' + esc(r.label) +
          ':</span> <a href="' + r.url + '">' + esc(r.title) + '</a>' +
          (r.note ? ' <span class="muted">(' + esc(r.note) + ')</span>' : '') + '</li>';
      }).join("") + '</ul></div>';
  }

  function mount(el, opts) {
    opts = opts || {};
    var loading = el.parentElement.querySelector(".graph-loading");
    return fetch(opts.url, { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (loading) loading.remove();
        var cy = cytoscape({
          container: el,
          elements: { nodes: data.nodes, edges: data.edges },
          style: styles(opts.mini),
          layout: {
            name: "cose", animate: false, randomize: true, padding: 24,
            nodeRepulsion: function () { return opts.mini ? 9000 : 60000; },
            idealEdgeLength: function () { return opts.mini ? 70 : 130; },
            edgeElasticity: function () { return 80; },
            gravity: 0.35, numIter: 1500
          },
          minZoom: 0.15, maxZoom: 3, wheelSensitivity: 0.25
        });

        function clearHighlight() { cy.elements().removeClass("faded hl show-label"); }

        function highlight(node) {
          clearHighlight();
          var hood = node.closedNeighborhood();
          cy.elements().not(hood).addClass("faded");
          hood.addClass("hl");
          node.connectedEdges().addClass("show-label");
        }

        cy.on("tap", "node", function (evt) {
          var node = evt.target;
          if (opts.mini) { window.location = node.data("url"); return; }
          highlight(node);
          if (opts.info) renderInfo(opts.info, node);
        });
        cy.on("tap", function (evt) { if (evt.target === cy) clearHighlight(); });
        cy.on("mouseover", "edge", function (e) { e.target.addClass("show-label"); });
        cy.on("mouseout", "edge", function (e) {
          if (!e.target.hasClass("hl")) e.target.removeClass("show-label");
        });

        // фильтр по типам
        (opts.typeInputs || []).forEach(function (input) {
          input.addEventListener("change", function () {
            var hidden = {};
            opts.typeInputs.forEach(function (i) { if (!i.checked) hidden[i.value] = true; });
            cy.batch(function () {
              cy.nodes().forEach(function (n) {
                n.style("display", hidden[n.data("type")] ? "none" : "element");
              });
            });
          });
        });

        // поиск узла
        if (opts.search) {
          opts.search.addEventListener("input", function () {
            var q = opts.search.value.trim().toLowerCase();
            if (q.length < 2) { clearHighlight(); return; }
            var found = cy.nodes().filter(function (n) {
              return n.data("label").toLowerCase().indexOf(q) !== -1;
            });
            if (found.length) {
              clearHighlight();
              cy.elements().not(found).addClass("faded");
              found.addClass("hl");
              cy.animate({ fit: { eles: found, padding: 80 }, duration: 300 });
              if (found.length === 1 && opts.info) renderInfo(opts.info, found[0]);
            }
          });
        }

        // фокусный узел
        var focus = cy.nodes("[?focus]");
        if (focus.length) {
          if (opts.info) renderInfo(opts.info, focus[0]);
          if (!opts.mini) highlight(focus[0]);
        }

        var counter = document.getElementById("graph-counter");
        if (counter) counter.textContent = data.nodes.length + " узлов · " + data.edges.length + " связей";

        var fitBtn = document.getElementById("graph-fit");
        if (fitBtn) fitBtn.addEventListener("click", function () { clearHighlight(); cy.fit(undefined, 24); });
        var relayout = document.getElementById("graph-relayout");
        if (relayout) relayout.addEventListener("click", function () {
          cy.layout({ name: "cose", animate: true, randomize: true, nodeRepulsion: function () { return 60000; },
                      idealEdgeLength: function () { return 130; }, gravity: 0.35 }).run();
        });
        var png = document.getElementById("graph-png");
        if (png) png.addEventListener("click", function () {
          var a = document.createElement("a");
          a.href = cy.png({ full: true, scale: 2, bg: "#ffffff" });
          a.download = "guy-ritchie-knowledge-graph.png";
          a.click();
        });
        return cy;
      })
      .catch(function (err) {
        if (loading) loading.textContent = "Не удалось загрузить граф: " + err;
      });
  }

  window.KBGraph = { mount: mount };
})();
