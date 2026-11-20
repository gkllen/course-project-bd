r"""
Ранжирование BM25F (полевой BM25, Robertson & Zaragoza, 2009).

Для термина t и документа d сначала считается взвешенная нормированная частота
по всем полям f:

              ⎲        tf(t, d, f)
    tf~(t,d) = ⎳  w_f · ─────────────────────────────
              f        1 − b + b · len(d, f) / avglen(f)

затем сатурация и IDF:

                   ⎲              tf~(t, d)
    score(q, d) =  ⎳  idf(t) · ───────────────
                  t∈q          k1 + tf~(t, d)

    idf(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))

Веса полей (settings.KB_SEARCH): заголовок 3.0, теги 2.0, аннотация 1.5,
атрибуты 1.0, содержание 1.0 — совпадение в заголовке ценнее, чем в тексте.

Поверх BM25F применяются эвристики:
  • все слова запроса есть в заголовке — ×1.25, плюс точная фраза — ещё ×1.2;
  • бонус связности узла графа: × (1 + 0.04 · ln(1 + степень));
  • префиксные расширения термина (для незаконченных слов) учитываются с весом 0.5.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Avg

from .models import FieldLength, Posting, Term

PREFIX_WEIGHT = 0.5
MIN_PREFIX_LEN = 3


@dataclass
class ScoredDoc:
    entry_id: int
    score: float = 0.0
    bm25: float = 0.0
    fields: dict = field(default_factory=lambda: defaultdict(float))  # вклад полей
    matched_terms: set = field(default_factory=set)
    bonuses: dict = field(default_factory=dict)


def _params():
    cfg = settings.KB_SEARCH
    return cfg["FIELD_WEIGHTS"], cfg["K1"], cfg["B"]


def expand_terms(query_terms):
    """
    Сопоставить термины запроса со словарём индекса.
    Возвращает {термин_словаря: (термин_запроса, коэффициент)}.
    Точное совпадение → 1.0; если точного нет (слово не дописано) — префиксные
    расширения с коэффициентом PREFIX_WEIGHT.
    """
    exact = set(Term.objects.filter(text__in=query_terms).values_list("text", flat=True))
    mapping = {t: (t, 1.0) for t in exact}
    for qt in query_terms:
        if qt in exact or len(qt) < MIN_PREFIX_LEN:
            continue
        for t in Term.objects.filter(text__startswith=qt).values_list("text", flat=True)[:20]:
            mapping.setdefault(t, (qt, PREFIX_WEIGHT))
    return mapping


def bm25f(query_terms, candidate_ids=None):
    """
    Посчитать BM25F для всех документов, содержащих хотя бы один термин запроса.
    Возвращает {entry_id: ScoredDoc}.
    """
    weights, k1, b = _params()
    mapping = expand_terms(query_terms)
    if not mapping:
        return {}

    n_docs = FieldLength.objects.values("entry_id").distinct().count() or 1
    avglen = {row["field"]: row["avg"] or 1.0
              for row in FieldLength.objects.values("field").annotate(avg=Avg("length"))}

    postings = Posting.objects.filter(term__text__in=mapping.keys())
    if candidate_ids is not None:
        postings = postings.filter(entry_id__in=candidate_ids)
    rows = list(postings.values_list("entry_id", "field", "tf", "term__text", "term__df"))

    doc_ids = {r[0] for r in rows}
    lengths = defaultdict(dict)
    for eid, f, n in FieldLength.objects.filter(entry_id__in=doc_ids).values_list(
            "entry_id", "field", "length"):
        lengths[eid][f] = n

    # tf~ по (документ, термин) и разбивка по полям
    tf_tilde = defaultdict(float)
    field_part = defaultdict(lambda: defaultdict(float))
    dfs = {}
    for eid, f, tf, term, df in rows:
        norm = 1 - b + b * lengths[eid].get(f, 0) / avglen.get(f, 1.0)
        val = weights.get(f, 1.0) * tf / norm
        tf_tilde[(eid, term)] += val
        field_part[(eid, term)][f] += val
        dfs[term] = df

    docs = {}
    for (eid, term), tft in tf_tilde.items():
        qterm, coef = mapping[term]
        df = dfs[term]
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        contrib = coef * idf * tft / (k1 + tft)
        doc = docs.setdefault(eid, ScoredDoc(eid))
        doc.bm25 += contrib
        doc.matched_terms.add(term)
        doc.matched_terms.add(qterm)
        # вклад распределяем по полям пропорционально их доле в tf~
        for f, part in field_part[(eid, term)].items():
            doc.fields[f] += contrib * part / tft
    for d in docs.values():
        d.score = d.bm25
    return docs


def apply_bonuses(docs, query_terms, raw_query, entries, degrees):
    """Эвристические бонусы: заголовок, точная фраза, связность в графе."""
    from .normalizer import normalize

    phrase = " ".join(normalize(raw_query))
    for eid, doc in docs.items():
        entry = entries.get(eid)
        if entry is None:
            continue
        title_terms = normalize(f"{entry.title} {entry.original_title}")
        mult = 1.0
        if query_terms and all(t in title_terms for t in query_terms):
            mult *= 1.25
            doc.bonuses["все слова в заголовке"] = "×1.25"
            if len(query_terms) > 1 and phrase and phrase in " ".join(title_terms):
                mult *= 1.2
                doc.bonuses["точная фраза"] = "×1.2"
        deg = degrees.get(eid, 0)
        g = 1 + 0.04 * math.log1p(deg)
        mult *= g
        doc.bonuses["связность графа"] = f"×{g:.3f} (степень {deg})"
        doc.score = doc.bm25 * mult
    return docs
