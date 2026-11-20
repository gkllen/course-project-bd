"""
Автоматическая переиндексация при изменениях в админке.

При массовой загрузке (seed_kb) сигналы отключаются контекстным менеджером
indexing_disabled(), после чего индекс перестраивается один раз целиком.
"""
import threading
from contextlib import contextmanager

from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from knowledge.models import KnowledgeEntry, Tag

from . import indexer

_state = threading.local()


def _enabled():
    return not getattr(_state, "disabled", False)


@contextmanager
def indexing_disabled():
    prev = getattr(_state, "disabled", False)
    _state.disabled = True
    try:
        yield
    finally:
        _state.disabled = prev


def _reindex_later(entry_id):
    def run():
        entry = (KnowledgeEntry.objects.filter(pk=entry_id)
                 .select_related("entity_type").prefetch_related("tags").first())
        if entry:
            indexer.index_entry(entry)
    transaction.on_commit(run)


@receiver(post_save, sender=KnowledgeEntry)
def entry_saved(sender, instance, raw=False, **kwargs):
    if _enabled() and not raw:
        _reindex_later(instance.pk)


@receiver(post_delete, sender=KnowledgeEntry)
def entry_deleted(sender, instance, **kwargs):
    # постинги удалились каскадом — осталось пересчитать df
    if _enabled():
        transaction.on_commit(lambda: indexer._refresh_df(
            indexer.Term.objects.filter(df__gt=0).values_list("id", flat=True)))


@receiver(m2m_changed, sender=KnowledgeEntry.tags.through)
def entry_tags_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if not _enabled() or action not in ("post_add", "post_remove", "post_clear"):
        return
    if reverse:  # изменили со стороны тега
        ids = pk_set or []
        for eid in ids:
            _reindex_later(eid)
    else:
        _reindex_later(instance.pk)


@receiver(post_save, sender=Tag)
def tag_saved(sender, instance, created, **kwargs):
    if _enabled() and not created:
        for eid in instance.entries.values_list("pk", flat=True):
            _reindex_later(eid)
