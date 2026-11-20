"""
Таблицы собственного инвертированного индекса (хранятся в той же SQLite).

    Term         — словарь: термин (лемма) и документная частота df
    Posting      — постинг-лист: (термин, запись, поле) → частота tf
    FieldLength  — длина каждого поля каждой записи (в терминах), нужна для BM25
"""
from django.db import models

from knowledge.models import KnowledgeEntry

FIELD_CHOICES = [
    ("title", "Заголовок"),
    ("tags", "Теги"),
    ("summary", "Аннотация"),
    ("meta", "Атрибуты"),
    ("content", "Содержание"),
]


class Term(models.Model):
    text = models.CharField("Термин", max_length=128, unique=True)
    df = models.PositiveIntegerField("Документная частота", default=0)

    class Meta:
        verbose_name = "Термин словаря"
        verbose_name_plural = "Словарь индекса"
        ordering = ["text"]

    def __str__(self):
        return f"{self.text} (df={self.df})"


class Posting(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="postings")
    entry = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE, related_name="postings")
    field = models.CharField("Поле", max_length=16, choices=FIELD_CHOICES)
    tf = models.PositiveIntegerField("Частота в поле")

    class Meta:
        verbose_name = "Постинг"
        verbose_name_plural = "Постинги"
        constraints = [models.UniqueConstraint(fields=["term", "entry", "field"],
                                               name="uniq_posting")]

    def __str__(self):
        return f"{self.term.text} → {self.entry_id}.{self.field} tf={self.tf}"


class FieldLength(models.Model):
    entry = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE, related_name="field_lengths")
    field = models.CharField("Поле", max_length=16, choices=FIELD_CHOICES)
    length = models.PositiveIntegerField("Длина (терминов)")

    class Meta:
        verbose_name = "Длина поля"
        verbose_name_plural = "Длины полей"
        constraints = [models.UniqueConstraint(fields=["entry", "field"], name="uniq_field_length")]
