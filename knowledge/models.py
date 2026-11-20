"""
Модели базы знаний — семантическая сеть.

Узлы графа: KnowledgeEntry (типизированы через EntityType).
Рёбра графа: Relation (направленные, типизированы через RelationType).
Ключевые слова: Tag (M2M к узлам).
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.html import escape
from django.utils.text import slugify

# Таблица транслитерации для генерации slug из русских названий
_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def make_slug(text: str) -> str:
    """Slug из произвольной (в т.ч. кириллической) строки."""
    return slugify(text.lower().translate(_TRANSLIT))[:200] or "entry"


class EntityType(models.Model):
    """Тип сущности (класс онтологии): Фильм, Персонаж, Актёр, Киноприём..."""

    code = models.SlugField("Код", max_length=32, unique=True)
    name = models.CharField("Название", max_length=64)
    name_plural = models.CharField("Название (мн. ч.)", max_length=64)
    description = models.TextField("Описание класса", blank=True)
    color = models.CharField("Цвет (HEX)", max_length=7, default="#025e8d",
                             help_text="Цвет бейджа и узла на графе")
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Тип сущности"
        verbose_name_plural = "Типы сущностей"

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Ключевое слово / тег."""

    name = models.CharField("Тег", max_length=64, unique=True)
    slug = models.SlugField("Slug", max_length=80, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Тег"
        verbose_name_plural = "Теги"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = make_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class KnowledgeEntry(models.Model):
    """Запись базы знаний (узел семантической сети)."""

    title = models.CharField("Заголовок", max_length=255)
    original_title = models.CharField("Оригинальное название", max_length=255, blank=True)
    slug = models.SlugField("Slug", max_length=200, unique=True, blank=True)
    entity_type = models.ForeignKey(EntityType, on_delete=models.PROTECT,
                                    related_name="entries", verbose_name="Тип сущности")
    summary = models.TextField("Аннотация", help_text="Краткое описание (1–3 предложения)")
    content = models.TextField(
        "Содержание", blank=True,
        help_text="Структурированный текст. Секции начинаются со строки «## Заголовок секции».",
    )
    year = models.PositiveSmallIntegerField("Год", null=True, blank=True, db_index=True)
    genres = models.JSONField("Жанры", default=list, blank=True,
                              help_text='Список строк, например ["криминал", "комедия"]')
    metadata_json = models.JSONField(
        "Атрибуты", default=dict, blank=True,
        help_text='Словарь характеристик: {"Бюджет": "$22 млн", "Длительность": "113 мин"}',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="entries", verbose_name="Теги")
    kb_id = models.CharField("Идентификатор БЗ", max_length=64, unique=True,
                             blank=True, null=True, editable=False)
    views = models.PositiveIntegerField("Просмотры", default=0, editable=False)
    is_published = models.BooleanField("Опубликовано", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Запись базы знаний"
        verbose_name_plural = "Записи базы знаний"
        indexes = [models.Index(fields=["entity_type", "year"])]

    def __str__(self):
        return f"{self.title} ({self.entity_type.name})" if self.entity_type_id else self.title

    # ---------- сохранение ----------
    def save(self, *args, **kwargs):
        if not self.slug:
            base = make_slug(self.original_title or self.title)
            slug, n = base, 2
            while KnowledgeEntry.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)
        if not self.kb_id:
            # DOI-подобный код: 10.5555/gr-kb.film.2019.0007
            self.kb_id = (f"{settings.KB_ID_PREFIX}.{self.entity_type.code}."
                          f"{self.year or '0000'}.{self.pk:04d}")
            KnowledgeEntry.objects.filter(pk=self.pk).update(kb_id=self.kb_id)

    def get_absolute_url(self):
        return reverse("portal:entry", kwargs={"slug": self.slug})

    # ---------- структурированное содержание ----------
    def sections(self):
        """
        Разбирает content на секции по маркерам «## Заголовок».
        Возвращает список dict(anchor, title, paragraphs).
        """
        result, current = [], None
        for raw in (self.content or "").splitlines():
            line = raw.strip()
            if line.startswith("## "):
                title = line[3:].strip()
                current = {"anchor": f"sec-{len(result) + 1}", "title": title, "paragraphs": []}
                result.append(current)
            elif line:
                if current is None:
                    current = {"anchor": "sec-1", "title": "Описание", "paragraphs": []}
                    result.append(current)
                current["paragraphs"].append(line)
        return result

    def plain_content(self) -> str:
        """Текст содержимого без маркеров разметки (для индексации и сниппетов)."""
        return re.sub(r"^\s*##\s*", "", self.content or "", flags=re.M)

    def metadata_text(self) -> str:
        """Атрибуты и жанры одной строкой — отдельное поле индекса."""
        parts = [str(v) for v in (self.metadata_json or {}).values()]
        parts += list(self.genres or [])
        if self.original_title:
            parts.append(self.original_title)
        return " ".join(parts)

    # ---------- связи ----------
    def related_entries(self):
        """
        Все связи узла в обе стороны.
        Возвращает список dict(relation, entry, label, direction).
        Для входящих связей используется обратное имя типа связи.
        """
        items = []
        out_qs = self.outgoing.select_related("target__entity_type", "relation_type")
        in_qs = self.incoming.select_related("source__entity_type", "relation_type")
        for r in out_qs:
            if r.target.is_published:
                items.append({"relation": r, "entry": r.target,
                              "label": r.relation_type.name, "direction": "out"})
        for r in in_qs:
            if r.source.is_published:
                items.append({"relation": r, "entry": r.source,
                              "label": r.relation_type.inverse_name or r.relation_type.name,
                              "direction": "in"})
        items.sort(key=lambda x: (x["entry"].entity_type.order, x["label"], x["entry"].title))
        return items

    def degree(self) -> int:
        return self.outgoing.count() + self.incoming.count()

    def to_dict(self, with_relations=True) -> dict:
        """Сериализация записи (экспорт JSON / API)."""
        data = {
            "kb_id": self.kb_id,
            "slug": self.slug,
            "title": self.title,
            "original_title": self.original_title,
            "type": {"code": self.entity_type.code, "name": self.entity_type.name},
            "year": self.year,
            "genres": self.genres,
            "summary": self.summary,
            "sections": [{"title": s["title"], "text": "\n".join(s["paragraphs"])}
                         for s in self.sections()],
            "attributes": self.metadata_json,
            "tags": [t.name for t in self.tags.all()],
            "url": self.get_absolute_url(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if with_relations:
            data["relations"] = [
                {"relation": it["label"], "direction": it["direction"],
                 "relation_code": it["relation"].relation_type.code,
                 "target": {"slug": it["entry"].slug, "title": it["entry"].title,
                            "type": it["entry"].entity_type.code},
                 "note": it["relation"].note}
                for it in self.related_entries()
            ]
        return data

    def citation(self) -> str:
        """Библиографическая строка в духе ГОСТ / Springer «Cite this»."""
        year = f" ({self.year})" if self.year else ""
        return (f"{escape(self.title)}{year} // База знаний «Фильмография и творчество Гая Ричи». "
                f"[Электронный ресурс]. ID: {self.kb_id}.")


class RelationType(models.Model):
    """Тип семантической связи (предикат)."""

    code = models.SlugField("Код", max_length=48, unique=True)
    name = models.CharField("Прямое имя", max_length=64, help_text="Например: «снялся в»")
    inverse_name = models.CharField("Обратное имя", max_length=64, blank=True,
                                    help_text="Например: «в ролях»")
    is_symmetric = models.BooleanField("Симметричная", default=False)
    description = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Тип связи"
        verbose_name_plural = "Типы связей"

    def __str__(self):
        return self.name


class Relation(models.Model):
    """Направленное ребро семантической сети: source —[relation_type]→ target."""

    source = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE,
                               related_name="outgoing", verbose_name="Источник")
    target = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE,
                               related_name="incoming", verbose_name="Цель")
    relation_type = models.ForeignKey(RelationType, on_delete=models.PROTECT,
                                      related_name="relations", verbose_name="Тип связи")
    weight = models.FloatField("Вес", default=1.0, help_text="Сила связи 0..1")
    note = models.CharField("Примечание", max_length=255, blank=True,
                            help_text="Например: «роль второго плана»")
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Связь"
        verbose_name_plural = "Связи"
        constraints = [
            models.UniqueConstraint(fields=["source", "target", "relation_type"],
                                    name="uniq_relation_triple"),
            models.CheckConstraint(condition=~models.Q(source=models.F("target")),
                                   name="relation_no_self_loop"),
        ]

    def clean(self):
        if self.source_id and self.source_id == self.target_id:
            raise ValidationError("Связь не может вести из записи в саму себя.")

    def __str__(self):
        return f"{self.source.title} —[{self.relation_type.name}]→ {self.target.title}"
