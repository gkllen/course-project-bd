"""
Построение инвертированного индекса.

Каждая запись раскладывается на поля, каждое поле нормализуется (лемматизация),
для каждого термина сохраняется tf в поле. После изменения пересчитывается df
затронутых терминов.
"""
from collections import Counter

from django.db import transaction
from django.db.models import Count

from knowledge.models import KnowledgeEntry

from .models import FieldLength, Posting, Term
from .normalizer import normalize


def entry_fields(entry: KnowledgeEntry) -> dict:
    """Текст записи, разложенный по полям индекса."""
    return {
        "title": f"{entry.title} {entry.original_title}",
        "tags": " ".join(t.name for t in entry.tags.all()),
        "summary": entry.summary,
        "meta": entry.metadata_text(),
        "content": entry.plain_content(),
    }


def _analyze(entry):
    """{поле: Counter(термин → tf)} и {поле: длина}."""
    counters, lengths = {}, {}
    for field, text in entry_fields(entry).items():
        terms = normalize(text)
        counters[field] = Counter(terms)
        lengths[field] = len(terms)
    return counters, lengths


def _refresh_df(term_ids):
    """Пересчитать df для терминов; термины без постингов удалить."""
    term_ids = set(term_ids)
    if not term_ids:
        return
    counts = dict(Posting.objects.filter(term_id__in=term_ids)
                  .values("term_id").annotate(n=Count("entry_id", distinct=True))
                  .values_list("term_id", "n"))
    terms = list(Term.objects.filter(id__in=term_ids))
    for t in terms:
        t.df = counts.get(t.id, 0)
    Term.objects.bulk_update(terms, ["df"])
    Term.objects.filter(id__in=term_ids, df=0).delete()


def _get_terms(texts) -> dict:
    """Получить/создать термины словаря. Возвращает {text: id}."""
    texts = set(texts)
    existing = dict(Term.objects.filter(text__in=texts).values_list("text", "id"))
    missing = texts - existing.keys()
    if missing:
        Term.objects.bulk_create([Term(text=t) for t in missing], ignore_conflicts=True)
        existing.update(Term.objects.filter(text__in=missing).values_list("text", "id"))
    return existing


@transaction.atomic
def remove_entry(entry_id: int):
    old_terms = list(Posting.objects.filter(entry_id=entry_id).values_list("term_id", flat=True))
    Posting.objects.filter(entry_id=entry_id).delete()
    FieldLength.objects.filter(entry_id=entry_id).delete()
    _refresh_df(old_terms)


@transaction.atomic
def index_entry(entry: KnowledgeEntry):
    """(Пере)индексировать одну запись. Неопубликованные из индекса удаляются."""
    old_terms = set(Posting.objects.filter(entry_id=entry.pk).values_list("term_id", flat=True))
    Posting.objects.filter(entry_id=entry.pk).delete()
    FieldLength.objects.filter(entry_id=entry.pk).delete()

    if not entry.is_published:
        _refresh_df(old_terms)
        return

    counters, lengths = _analyze(entry)
    term_ids = _get_terms(t for c in counters.values() for t in c)
    Posting.objects.bulk_create([
        Posting(term_id=term_ids[term], entry_id=entry.pk, field=field, tf=tf)
        for field, counter in counters.items() for term, tf in counter.items()
    ])
    FieldLength.objects.bulk_create([
        FieldLength(entry_id=entry.pk, field=f, length=n) for f, n in lengths.items()
    ])
    _refresh_df(old_terms | set(term_ids.values()))


@transaction.atomic
def rebuild_index(verbose=False) -> dict:
    """Полная перестройка индекса по всем опубликованным записям."""
    Posting.objects.all().delete()
    FieldLength.objects.all().delete()
    Term.objects.all().delete()

    entries = (KnowledgeEntry.objects.filter(is_published=True)
               .select_related("entity_type").prefetch_related("tags"))
    analyzed = []
    vocabulary = set()
    for entry in entries:
        counters, lengths = _analyze(entry)
        analyzed.append((entry.pk, counters, lengths))
        for c in counters.values():
            vocabulary.update(c)
        if verbose:
            print(f"  · {entry.title}: {sum(lengths.values())} терминов")

    Term.objects.bulk_create([Term(text=t) for t in vocabulary], batch_size=1000)
    term_ids = dict(Term.objects.values_list("text", "id"))

    postings, field_lengths, df = [], [], Counter()
    for entry_id, counters, lengths in analyzed:
        seen = set()
        for field, counter in counters.items():
            for term, tf in counter.items():
                postings.append(Posting(term_id=term_ids[term], entry_id=entry_id,
                                        field=field, tf=tf))
                seen.add(term)
        df.update(seen)
        field_lengths += [FieldLength(entry_id=entry_id, field=f, length=n)
                          for f, n in lengths.items()]
    Posting.objects.bulk_create(postings, batch_size=2000)
    FieldLength.objects.bulk_create(field_lengths, batch_size=2000)

    terms = list(Term.objects.all())
    for t in terms:
        t.df = df[t.text]
    Term.objects.bulk_update(terms, ["df"], batch_size=1000)

    return {"documents": len(analyzed), "terms": len(vocabulary), "postings": len(postings)}
