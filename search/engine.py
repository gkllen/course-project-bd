"""
Фасад поискового движка: запрос → кандидаты (BM25F) → фильтры → фасеты →
сортировка → пагинация → сниппеты.
"""
import difflib
import math
import time
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Count

from knowledge.models import KnowledgeEntry, Relation, Tag

from .facets import Filters, apply_filters, compute_facets
from .models import Term
from .normalizer import normalize_query
from .ranking import apply_bonuses, bm25f, expand_terms
from .snippets import highlight, make_snippet

SORTS = {
    "relevance": "По релевантности",
    "newest": "Сначала новые",
    "oldest": "Сначала старые",
    "alpha": "По алфавиту",
}


@dataclass
class SearchHit:
    entry: KnowledgeEntry
    score: float
    title_html: str
    snippet_html: str
    explain: dict
    related: list


@dataclass
class SearchResponse:
    query: str
    terms: list
    total: int
    page: int
    pages: int
    sort: str
    hits: list
    facets: dict
    filters: Filters
    suggestion: str | None = None
    took_ms: float = 0.0
    expanded: dict = field(default_factory=dict)


def _degrees():
    out = {}
    for eid, n in Relation.objects.values_list("source_id").annotate(n=Count("id")):
        out[eid] = out.get(eid, 0) + n
    for eid, n in Relation.objects.values_list("target_id").annotate(n=Count("id")):
        out[eid] = out.get(eid, 0) + n
    return out


def _doc_attrs(entries):
    """Атрибуты документов для фасетов."""
    tags_by_entry = {}
    for eid, slug in KnowledgeEntry.tags.through.objects.filter(
            knowledgeentry_id__in=[e.pk for e in entries]).values_list(
            "knowledgeentry_id", "tag__slug"):
        tags_by_entry.setdefault(eid, []).append(slug)
    return [{
        "id": e.pk,
        "type": e.entity_type.code,
        "year": e.year,
        "decade": (e.year // 10 * 10) if e.year else None,
        "genres": [g.lower() for g in (e.genres or [])],
        "tags": tags_by_entry.get(e.pk, []),
    } for e in entries]


def did_you_mean(query_terms):
    """Исправление опечаток: ближайшие термины словаря (difflib, отношение ≥ 0.75)."""
    vocab = list(Term.objects.values_list("text", flat=True))
    fixed, changed = [], False
    for t in query_terms:
        if t in vocab:
            fixed.append(t)
            continue
        close = difflib.get_close_matches(t, vocab, n=1, cutoff=0.75)
        if close:
            fixed.append(close[0])
            changed = True
        else:
            fixed.append(t)
    return " ".join(fixed) if changed else None


_RELATED_PRIORITY = {"person": 0, "actor": 1, "character": 2, "film": 3}


def _short_related(entry, limit=3):
    """
    Связанные сущности для строки «авторов» в карточке результата (как у Springer):
    у фильма — режиссёр и актёры, у актёра — фильмы, у приёма — фильмы и т.д.
    """
    rel = entry.related_entries()
    rel.sort(key=lambda r: (_RELATED_PRIORITY.get(r["entry"].entity_type.code, 9),
                            r["direction"] != "in", -(r["entry"].year or 0)))
    return rel[:limit]


def search(query: str = "", filters: Filters | None = None, sort: str = "relevance",
           page: int = 1, page_size: int | None = None, with_related=True) -> SearchResponse:
    t0 = time.perf_counter()
    filters = filters or Filters()
    sort = sort if sort in SORTS else "relevance"
    page_size = page_size or settings.KB_SEARCH["PAGE_SIZE"]
    query = (query or "").strip()
    terms = normalize_query(query)

    base_qs = KnowledgeEntry.objects.filter(is_published=True).select_related("entity_type")
    degrees = _degrees()

    if terms:
        scored = bm25f(terms)
        entries = {e.pk: e for e in base_qs.filter(pk__in=scored.keys())}
        scored = {k: v for k, v in scored.items() if k in entries}
        apply_bonuses(scored, terms, query, entries, degrees)
    else:
        # Пустой запрос — каталог: «релевантность» = центральность узла + популярность
        entries = {e.pk: e for e in base_qs}
        scored = None

    candidates = _doc_attrs(list(entries.values()))
    tag_names = dict(Tag.objects.values_list("slug", "name"))
    facets = compute_facets(candidates, filters, tag_names)
    filtered_ids = [d["id"] for d in apply_filters(candidates, filters)]
    items = [entries[i] for i in filtered_ids]

    def score_of(e):
        if scored is not None:
            return scored[e.pk].score
        return math.log1p(degrees.get(e.pk, 0)) + 0.1 * math.log1p(e.views)

    if sort == "newest":
        items.sort(key=lambda e: (e.year is None, -(e.year or 0), -score_of(e)))
    elif sort == "oldest":
        items.sort(key=lambda e: (e.year is None, e.year or 0, -score_of(e)))
    elif sort == "alpha":
        items.sort(key=lambda e: e.title.lower())
    else:
        items.sort(key=lambda e: (-score_of(e), e.title.lower()))

    total = len(items)
    pages = max(1, math.ceil(total / page_size))
    page = min(max(1, page), pages)
    page_items = items[(page - 1) * page_size: page * page_size]

    expanded = expand_terms(terms) if terms else {}
    prefixes = tuple(qt for qt in terms if qt not in expanded)
    all_terms = set(terms) | set(expanded.keys())

    hits = []
    for e in page_items:
        doc = scored.get(e.pk) if scored else None
        explain = {}
        if doc:
            explain = {
                "bm25f": round(doc.bm25, 4),
                "fields": {f: round(v, 4) for f, v in sorted(doc.fields.items(),
                                                              key=lambda x: -x[1])},
                "bonuses": doc.bonuses,
                "matched_terms": sorted(doc.matched_terms),
            }
        text = f"{e.summary} {e.plain_content()}"
        hits.append(SearchHit(
            entry=e,
            score=round(score_of(e), 3),
            title_html=highlight(e.title, all_terms, prefixes),
            snippet_html=make_snippet(text, all_terms, prefixes),
            explain=explain,
            related=_short_related(e) if with_related else [],
        ))

    suggestion = None
    if terms and total < 3:
        suggestion = did_you_mean(terms)

    return SearchResponse(
        query=query, terms=terms, total=total, page=page, pages=pages, sort=sort,
        hits=hits, facets=facets, filters=filters, suggestion=suggestion,
        took_ms=round((time.perf_counter() - t0) * 1000, 1),
        expanded={k: v[0] for k, v in expanded.items() if k != v[0]},
    )


def suggest(prefix: str, limit=8):
    """Живые подсказки: записи, у которых заголовок или его леммы начинаются с префикса."""
    prefix = (prefix or "").strip().lower().replace("ё", "е")
    if len(prefix) < 2:
        return []
    q_terms = normalize_query(prefix)
    out = []
    for e in KnowledgeEntry.objects.filter(is_published=True).select_related("entity_type"):
        title = f"{e.title} {e.original_title}".lower().replace("ё", "е")
        words = title.replace("«", " ").replace("»", " ").split()
        rank = None
        if title.startswith(prefix):
            rank = 0
        elif any(w.startswith(prefix) for w in words):
            rank = 1
        elif prefix in title:
            rank = 2
        elif q_terms:
            title_terms = normalize_query(title)
            if all(any(tt.startswith(qt) for tt in title_terms) for qt in q_terms):
                rank = 3
        if rank is not None:
            out.append((rank, e.title.lower(), e))
    out.sort(key=lambda x: (x[0], x[1]))
    return [{"title": e.title, "slug": e.slug, "url": e.get_absolute_url(),
             "type": e.entity_type.name, "type_code": e.entity_type.code,
             "color": e.entity_type.color, "year": e.year}
            for _, _, e in out[:limit]]
