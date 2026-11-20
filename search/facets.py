"""
Фасетная фильтрация (как на SpringerLink).

Счётчик у значения фасета = сколько записей найдётся, если добавить это значение,
при этом учитываются фильтры всех ДРУГИХ фасетов (disjunctive faceting):
выбор «Фильм» не обнуляет счётчик у «Актёр», а показывает, сколько станет
результатов при выборе обоих типов (внутри фасета значения объединяются по ИЛИ).
"""
from collections import Counter
from dataclasses import dataclass, field

from knowledge.models import EntityType


@dataclass
class Filters:
    types: list = field(default_factory=list)      # коды EntityType
    genres: list = field(default_factory=list)
    tags: list = field(default_factory=list)       # slug тегов
    decades: list = field(default_factory=list)    # 1990, 2000, ...
    year_from: int | None = None
    year_to: int | None = None

    @classmethod
    def from_querydict(cls, qd):
        def ints(values):
            out = []
            for v in values:
                try:
                    out.append(int(v))
                except (TypeError, ValueError):
                    pass
            return out

        def one_int(name):
            vals = ints([qd.get(name)])
            return vals[0] if vals else None

        return cls(
            types=[v for v in qd.getlist("type") if v],
            genres=[v for v in qd.getlist("genre") if v],
            tags=[v for v in qd.getlist("tag") if v],
            decades=ints(qd.getlist("decade")),
            year_from=one_int("year_from"),
            year_to=one_int("year_to"),
        )

    def is_empty(self):
        return not (self.types or self.genres or self.tags or self.decades
                    or self.year_from or self.year_to)

    def as_dict(self):
        return {"type": self.types, "genre": self.genres, "tag": self.tags,
                "decade": self.decades, "year_from": self.year_from, "year_to": self.year_to}


def _passes(doc, f: Filters, skip=None):
    """Проходит ли документ фильтры (кроме фасета skip)."""
    if skip != "type" and f.types and doc["type"] not in f.types:
        return False
    if skip != "genre" and f.genres and not set(f.genres) & set(doc["genres"]):
        return False
    if skip != "tag" and f.tags and not set(f.tags) & set(doc["tags"]):
        return False
    if skip != "decade" and f.decades and doc["decade"] not in f.decades:
        return False
    if skip != "year" and (f.year_from or f.year_to):
        y = doc["year"]
        if y is None:
            return False
        if f.year_from and y < f.year_from:
            return False
        if f.year_to and y > f.year_to:
            return False
    return True


def apply_filters(docs, f: Filters):
    return [d for d in docs if _passes(d, f)]


def compute_facets(docs, f: Filters, tag_names: dict, tag_limit=15):
    """
    docs — список dict(id, type, year, decade, genres, tags) кандидатов по запросу.
    Возвращает структуру фасетов для шаблона/API.
    """
    type_c, genre_c, tag_c, decade_c = Counter(), Counter(), Counter(), Counter()
    years = []
    for d in docs:
        if _passes(d, f, skip="type"):
            type_c[d["type"]] += 1
        if _passes(d, f, skip="genre"):
            genre_c.update(set(d["genres"]))
        if _passes(d, f, skip="tag"):
            tag_c.update(set(d["tags"]))
        if _passes(d, f, skip="decade") and d["decade"] is not None:
            decade_c[d["decade"]] += 1
        if _passes(d, f, skip="year") and d["year"]:
            years.append(d["year"])

    types = [{"value": et.code, "label": et.name_plural, "color": et.color,
              "count": type_c.get(et.code, 0), "selected": et.code in f.types}
             for et in EntityType.objects.all()]

    genres = [{"value": g, "label": g.capitalize(), "count": n, "selected": g in f.genres}
              for g, n in sorted(genre_c.items(), key=lambda x: (-x[1], x[0]))]
    for g in f.genres:  # выбранные значения показываем всегда
        if g not in genre_c:
            genres.append({"value": g, "label": g.capitalize(), "count": 0, "selected": True})

    top_tags = sorted(tag_c.items(), key=lambda x: (-x[1], tag_names.get(x[0], x[0])))
    tags = [{"value": s, "label": tag_names.get(s, s), "count": n, "selected": s in f.tags}
            for s, n in top_tags[:tag_limit]]
    for s in f.tags:
        if s not in {t["value"] for t in tags}:
            tags.append({"value": s, "label": tag_names.get(s, s),
                         "count": tag_c.get(s, 0), "selected": True})

    decades = [{"value": dec, "label": f"{dec}-е", "count": n, "selected": dec in f.decades}
               for dec, n in sorted(decade_c.items())]

    return {
        "type": types,
        "genre": genres,
        "tag": tags,
        "decade": decades,
        "year": {"min": min(years) if years else None, "max": max(years) if years else None,
                 "from": f.year_from, "to": f.year_to},
    }
