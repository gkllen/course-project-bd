"""
REST API (JSON) базы знаний.

    GET /api/search/?q=&type=&genre=&tag=&decade=&year_from=&year_to=&sort=&page=
    GET /api/suggest/?q=
    GET /api/entry/<slug>/
    GET /api/graph/?type=film&type=actor&focus=<slug>&depth=1
    GET /api/stats/
"""
from collections import deque

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from knowledge.models import EntityType, KnowledgeEntry, Relation, RelationType, Tag
from search.engine import SORTS, search, suggest
from search.facets import Filters


def _json(data, status=200):
    return JsonResponse(data, status=status, safe=False,
                        json_dumps_params={"ensure_ascii": False, "indent": 2})


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@require_GET
def api_search(request):
    res = search(
        query=request.GET.get("q", ""),
        filters=Filters.from_querydict(request.GET),
        sort=request.GET.get("sort", "relevance"),
        page=_int(request.GET.get("page"), 1),
        page_size=min(_int(request.GET.get("page_size"), 10), 100),
        with_related=False,
    )
    return _json({
        "query": res.query,
        "normalized_terms": res.terms,
        "prefix_expansions": res.expanded,
        "suggestion": res.suggestion,
        "total": res.total,
        "page": res.page,
        "pages": res.pages,
        "sort": res.sort,
        "sort_options": SORTS,
        "took_ms": res.took_ms,
        "filters": res.filters.as_dict(),
        "results": [{
            "slug": h.entry.slug,
            "kb_id": h.entry.kb_id,
            "title": h.entry.title,
            "type": h.entry.entity_type.code,
            "type_name": h.entry.entity_type.name,
            "year": h.entry.year,
            "score": h.score,
            "snippet_html": str(h.snippet_html),
            "explain": h.explain,
            "url": h.entry.get_absolute_url(),
        } for h in res.hits],
        "facets": res.facets,
    })


@require_GET
def api_suggest(request):
    return _json({"query": request.GET.get("q", ""),
                  "suggestions": suggest(request.GET.get("q", ""))})


@require_GET
def api_entry(request, slug):
    entry = get_object_or_404(
        KnowledgeEntry.objects.select_related("entity_type").prefetch_related("tags"),
        slug=slug, is_published=True)
    return _json(entry.to_dict())


def graph_data(types=None, focus=None, depth=1):
    """Узлы и рёбра графа знаний (формат Cytoscape.js)."""
    entries = KnowledgeEntry.objects.filter(is_published=True).select_related("entity_type")
    if types:
        entries = entries.filter(entity_type__code__in=types)
    nodes = {e.pk: e for e in entries}
    rels = [r for r in Relation.objects.select_related("relation_type")
            if r.source_id in nodes and r.target_id in nodes]

    if focus:
        center = next((e for e in nodes.values() if e.slug == focus), None)
        if center is None:
            return None
        adj = {}
        for r in rels:
            adj.setdefault(r.source_id, set()).add(r.target_id)
            adj.setdefault(r.target_id, set()).add(r.source_id)
        keep, queue = {center.pk: 0}, deque([center.pk])
        while queue:  # BFS на глубину depth
            cur = queue.popleft()
            if keep[cur] >= depth:
                continue
            for nb in adj.get(cur, ()):
                if nb not in keep:
                    keep[nb] = keep[cur] + 1
                    queue.append(nb)
        nodes = {k: v for k, v in nodes.items() if k in keep}
        rels = [r for r in rels if r.source_id in nodes and r.target_id in nodes]

    degree = {}
    for r in rels:
        degree[r.source_id] = degree.get(r.source_id, 0) + 1
        degree[r.target_id] = degree.get(r.target_id, 0) + 1

    return {
        "nodes": [{"data": {
            "id": f"n{e.pk}", "label": e.title, "slug": e.slug, "type": e.entity_type.code,
            "type_name": e.entity_type.name, "color": e.entity_type.color, "year": e.year,
            "summary": e.summary, "url": e.get_absolute_url(), "degree": degree.get(e.pk, 0),
            "focus": bool(focus and e.slug == focus),
        }} for e in nodes.values()],
        "edges": [{"data": {
            "id": f"e{r.pk}", "source": f"n{r.source_id}", "target": f"n{r.target_id}",
            "label": r.relation_type.name, "code": r.relation_type.code, "note": r.note,
            "inverse": r.relation_type.inverse_name or r.relation_type.name,
            "weight": r.weight,
        }} for r in rels],
        "legend": [{"code": t.code, "name": t.name_plural, "color": t.color}
                   for t in EntityType.objects.all()],
    }


@require_GET
def api_graph(request):
    data = graph_data(types=[t for t in request.GET.getlist("type") if t],
                      focus=request.GET.get("focus") or None,
                      depth=max(1, min(_int(request.GET.get("depth"), 1), 3)))
    if data is None:
        return _json({"error": "Запись не найдена"}, status=404)
    return _json(data)


def kb_stats():
    return {
        "entries": KnowledgeEntry.objects.filter(is_published=True).count(),
        "entity_types": EntityType.objects.count(),
        "relations": Relation.objects.count(),
        "relation_types": RelationType.objects.count(),
        "tags": Tag.objects.count(),
    }


@require_GET
def api_stats(request):
    return _json(kb_stats())
