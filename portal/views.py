"""Страницы портала (HTML)."""
import json

from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from knowledge.models import EntityType, KnowledgeEntry
from search.engine import SORTS, search
from search.facets import Filters

from . import api


def _types_with_counts():
    return EntityType.objects.annotate(n=Count("entries", filter=Q(entries__is_published=True)))


def home(request):
    published = KnowledgeEntry.objects.filter(is_published=True).select_related("entity_type")
    return render(request, "portal/home.html", {
        "stats": api.kb_stats(),
        "types": _types_with_counts(),
        "popular": published.order_by("-views", "title")[:6],
        "latest_films": published.filter(entity_type__code="film").order_by("-year")[:5],
        "techniques": published.filter(entity_type__code="technique").order_by("title")[:8],
        "recent": published.order_by("-updated_at", "-id")[:6],
        "examples": ["джентльмены", "стоп-кадр", "Стейтем", "Шерлок Холмс", "кокни"],
    })


def _page_window(page, pages, radius=2):
    """Номера страниц для пагинации с многоточиями (None)."""
    nums = sorted({1, pages, *range(max(1, page - radius), min(pages, page + radius) + 1)})
    out, prev = [], 0
    for n in nums:
        if n - prev > 1:
            out.append(None)
        out.append(n)
        prev = n
    return out


def search_page(request):
    filters = Filters.from_querydict(request.GET)
    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1
    res = search(query=request.GET.get("q", ""), filters=filters,
                 sort=request.GET.get("sort", "relevance"), page=page)

    type_names = {t["value"]: t["label"] for t in res.facets["type"]}
    tag_names = {t["value"]: t["label"] for t in res.facets["tag"]}
    active = (
        [("type", v, type_names.get(v, v)) for v in filters.types]
        + [("decade", v, f"{v}-е") for v in filters.decades]
        + [("genre", v, v.capitalize()) for v in filters.genres]
        + [("tag", v, tag_names.get(v, v)) for v in filters.tags]
    )
    if filters.year_from or filters.year_to:
        active.append(("year", None, f"Годы: {filters.year_from or '…'}–{filters.year_to or '…'}"))

    return render(request, "portal/search.html", {
        "res": res,
        "q": res.query,
        "sorts": SORTS,
        "active_filters": active,
        "max_score": max((h.score for h in res.hits), default=0),
        "page_window": _page_window(res.page, res.pages),
    })


def entry_detail(request, slug):
    entry = get_object_or_404(
        KnowledgeEntry.objects.select_related("entity_type").prefetch_related("tags"),
        slug=slug, is_published=True)
    # update() не трогает updated_at и не вызывает переиндексацию
    KnowledgeEntry.objects.filter(pk=entry.pk).update(views=F("views") + 1)

    related = entry.related_entries()
    groups = {}
    for item in related:
        et = item["entry"].entity_type
        groups.setdefault(et.pk, {"type": et, "items": []})["items"].append(item)
    rel_groups = sorted(groups.values(), key=lambda g: g["type"].order)

    sections = entry.sections()
    toc = ([{"anchor": "abstract", "title": "Аннотация"}]
           + [{"anchor": s["anchor"], "title": s["title"]} for s in sections])
    if entry.metadata_json:
        toc.append({"anchor": "attributes", "title": "Характеристики"})
    if related:
        toc.append({"anchor": "related", "title": "Связанные сущности"})
    toc.append({"anchor": "cite", "title": "Цитирование и экспорт"})

    return render(request, "portal/entry_detail.html", {
        "entry": entry,
        "sections": sections,
        "rel_groups": rel_groups,
        "rel_total": len(related),
        "toc": toc,
        "views": entry.views + 1,
    })


def entry_export(request, slug):
    entry = get_object_or_404(KnowledgeEntry.objects.select_related("entity_type"),
                              slug=slug, is_published=True)
    resp = HttpResponse(json.dumps(entry.to_dict(), ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{entry.slug}.json"'
    return resp


def graph_page(request):
    focus = request.GET.get("focus") or ""
    focus_entry = None
    if focus:
        focus_entry = KnowledgeEntry.objects.filter(slug=focus, is_published=True).first()
    try:
        depth = max(1, min(int(request.GET.get("depth", 1)), 3))
    except ValueError:
        depth = 1
    return render(request, "portal/graph.html", {
        "types": _types_with_counts(),
        "focus_entry": focus_entry,
        "depth": depth,
    })


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)
