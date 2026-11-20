"""
python manage.py seed_kb [--flush]

Наполняет базу знаний: онтология (типы сущностей и связей), записи
(фильмы, персонажи, актёры, создатели, приёмы, темы, локации, цитаты/факты)
и семантические связи между ними. Затем перестраивает поисковый индекс.

Команда идемпотентна: повторный запуск обновляет записи по slug и не
создаёт дубликатов связей. Флаг --flush полностью очищает базу знаний.
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import EntityType, KnowledgeEntry, Relation, RelationType, Tag
from search.indexer import rebuild_index
from search.signals import indexing_disabled

from .seed_data.characters import CHARACTERS
from .seed_data.concepts import LOCATIONS, TECHNIQUES, THEMES
from .seed_data.films import FILMS
from .seed_data.people import ACTORS, CREW
from .seed_data.quotes import QUOTES
from .seed_data.relations import EXTRA_RELATIONS
from .seed_data.schema import ENTITY_TYPES, RELATION_TYPES


class Command(BaseCommand):
    help = "Наполнить базу знаний фильмографией и творчеством Гая Ричи."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Удалить все данные базы знаний перед загрузкой.")

    def handle(self, *args, **options):
        with indexing_disabled(), transaction.atomic():
            if options["flush"]:
                self._flush()
            self.types = self._load_entity_types()
            self.rtypes = self._load_relation_types()
            self.entries = {}
            self.errors = []
            self.rel_count = Counter()

            self._load_entries("film", FILMS)
            self._load_entries("person", CREW)
            self._load_entries("actor", ACTORS)
            self._load_entries("character", CHARACTERS)
            self._load_entries("technique", TECHNIQUES)
            self._load_entries("theme", THEMES)
            self._load_entries("location", LOCATIONS)
            self._load_entries("quote", QUOTES)

            self._film_relations()
            self._character_relations()
            self._quote_relations()
            for src, code, tgt, note in EXTRA_RELATIONS:
                self._rel(src, code, tgt, note)

            if self.errors:
                raise CommandError("Ошибки в данных seed:\n  " + "\n  ".join(self.errors))
            self._set_popularity()

        stats = rebuild_index()
        self._report(stats)

    # ------------------------------------------------------------------ helpers
    def _flush(self):
        Relation.objects.all().delete()
        KnowledgeEntry.objects.all().delete()
        Tag.objects.all().delete()
        RelationType.objects.all().delete()
        EntityType.objects.all().delete()
        self.stdout.write(self.style.WARNING("База знаний очищена."))

    def _load_entity_types(self):
        out = {}
        for order, (code, name, plural, color, descr) in enumerate(ENTITY_TYPES, start=1):
            out[code], _ = EntityType.objects.update_or_create(
                code=code, defaults={"name": name, "name_plural": plural, "color": color,
                                     "description": descr, "order": order})
        return out

    def _load_relation_types(self):
        out = {}
        for code, name, inverse, symmetric, descr in RELATION_TYPES:
            out[code], _ = RelationType.objects.update_or_create(
                code=code, defaults={"name": name, "inverse_name": inverse,
                                     "is_symmetric": symmetric, "description": descr})
        return out

    def _load_entries(self, type_code, items):
        etype = self.types[type_code]
        for item in items:
            slug = item["slug"]
            if slug in self.entries:
                self.errors.append(f"дублирующийся slug «{slug}»")
                continue
            entry, _ = KnowledgeEntry.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": item["title"],
                    "original_title": item.get("original", ""),
                    "entity_type": etype,
                    "summary": item["summary"],
                    "content": item.get("content", "").strip(),
                    "year": item.get("year"),
                    "genres": item.get("genres", []),
                    "metadata_json": item.get("attrs", {}),
                    "is_published": True,
                },
            )
            tags = [Tag.objects.get_or_create(name=name)[0] for name in item.get("tags", [])]
            entry.tags.set(tags)
            self.entries[slug] = entry

    def _rel(self, src, code, tgt, note="", weight=1.0):
        s, t = self.entries.get(src), self.entries.get(tgt)
        if s is None or t is None:
            missing = src if s is None else tgt
            self.errors.append(f"связь {src} —{code}→ {tgt}: нет записи «{missing}»")
            return
        if s == t:
            return
        rtype = self.rtypes[code]
        if rtype.is_symmetric and Relation.objects.filter(
                source=t, target=s, relation_type=rtype).exists():
            return  # симметричную связь храним один раз
        _, created = Relation.objects.update_or_create(
            source=s, target=t, relation_type=rtype,
            defaults={"note": note, "weight": weight})
        if created:
            self.rel_count[code] += 1

    # ------------------------------------------------------------ relations
    def _film_relations(self):
        for film in FILMS:
            fs = film["slug"]
            for actor, character, role in film.get("cast", []):
                self._rel(actor, "acted_in", fs, role)
                if character:
                    self._rel(actor, "played", character, film["title"])
            for person, code in film.get("crew", []):
                self._rel(person, code, fs)
            for tech in film.get("techniques", []):
                self._rel(fs, "uses_technique", tech)
            for theme in film.get("themes", []):
                self._rel(fs, "explores_theme", theme)
            for loc in film.get("locations", []):
                self._rel(fs, "set_in", loc)
            for ch in film.get("extra_characters", []):
                self._rel(ch, "character_of", fs)

    def _character_relations(self):
        for ch in CHARACTERS:
            for film in ch.get("films", []):
                self._rel(ch["slug"], "character_of", film)
            for theme in ch.get("themes", []):
                self._rel(ch["slug"], "embodies", theme, weight=0.7)

    def _quote_relations(self):
        for q in QUOTES:
            if q.get("film"):
                self._rel(q["slug"], "quote_from", q["film"])
            if q.get("character"):
                self._rel(q["slug"], "said_by", q["character"])
            for target in q.get("about", []):
                self._rel(q["slug"], "fact_about", target)

    def _set_popularity(self):
        """Детерминированная «популярность» для блока «Популярное»: по степени узла."""
        degree = Counter()
        for s, t in Relation.objects.values_list("source_id", "target_id"):
            degree[s] += 1
            degree[t] += 1
        for slug, entry in self.entries.items():
            bonus = 60 if entry.entity_type.code == "film" else 0
            KnowledgeEntry.objects.filter(pk=entry.pk).update(views=20 + 9 * degree[entry.pk] + bonus)

    def _report(self, stats):
        by_type = Counter(KnowledgeEntry.objects.values_list("entity_type__name_plural", flat=True))
        self.stdout.write(self.style.SUCCESS("База знаний наполнена."))
        for name, n in by_type.most_common():
            self.stdout.write(f"  {name:<28} {n:>4}")
        self.stdout.write(f"  {'Записей всего':<28} {sum(by_type.values()):>4}")
        self.stdout.write(f"  {'Тегов':<28} {Tag.objects.count():>4}")
        self.stdout.write(f"  {'Связей всего':<28} {Relation.objects.count():>4}"
                          f"  (новых: {sum(self.rel_count.values())})")
        self.stdout.write(self.style.SUCCESS(
            f"Индекс: {stats['documents']} документов, {stats['terms']} терминов, "
            f"{stats['postings']} постингов."))
