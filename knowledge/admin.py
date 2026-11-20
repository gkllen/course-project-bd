"""Админ-панель — рабочее место инженера знаний."""
import json

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import EntityType, KnowledgeEntry, Relation, RelationType, Tag


def _badge(entity_type):
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;border-radius:2px;'
        'font-size:11px;white-space:nowrap">{}</span>',
        entity_type.color, entity_type.name,
    )


@admin.register(EntityType)
class EntityTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "colored", "order", "entries_count")
    list_editable = ("order",)
    prepopulated_fields = {"code": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("entries"))

    @admin.display(description="Цвет")
    def colored(self, obj):
        return _badge(obj)

    @admin.display(description="Записей", ordering="_n")
    def entries_count(self, obj):
        return obj._n


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "entries_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("entries"))

    @admin.display(description="Записей", ordering="_n")
    def entries_count(self, obj):
        return obj._n


@admin.register(RelationType)
class RelationTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "inverse_name", "code", "is_symmetric", "usage")
    search_fields = ("name", "inverse_name", "code")
    prepopulated_fields = {"code": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("relations"))

    @admin.display(description="Использований", ordering="_n")
    def usage(self, obj):
        return obj._n


class OutgoingRelationInline(admin.TabularInline):
    model = Relation
    fk_name = "source"
    extra = 1
    autocomplete_fields = ("target", "relation_type")
    fields = ("relation_type", "target", "weight", "note")
    verbose_name = "Исходящая связь"
    verbose_name_plural = "Исходящие связи (эта запись → другая)"


class IncomingRelationInline(admin.TabularInline):
    model = Relation
    fk_name = "target"
    extra = 0
    autocomplete_fields = ("source", "relation_type")
    fields = ("source", "relation_type", "weight", "note")
    verbose_name = "Входящая связь"
    verbose_name_plural = "Входящие связи (другая запись → эта)"


class PrettyJSONWidget(forms.Textarea):
    """Показывает JSON с отступами и кириллицей без \\u-экранирования."""

    def format_value(self, value):
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return value


class KnowledgeEntryForm(forms.ModelForm):
    class Meta:
        model = KnowledgeEntry
        fields = "__all__"
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3, "cols": 100}),
            "content": forms.Textarea(attrs={"rows": 18, "cols": 100}),
            "metadata_json": PrettyJSONWidget(attrs={"rows": 8, "cols": 80}),
            "genres": PrettyJSONWidget(attrs={"rows": 2, "cols": 80}),
        }


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    form = KnowledgeEntryForm
    list_display = ("title", "type_badge", "year", "kb_id", "relations_count",
                    "views", "is_published", "updated_at")
    list_display_links = ("title",)
    list_filter = ("entity_type", "is_published", "year", "tags")
    list_editable = ("is_published",)
    search_fields = ("title", "original_title", "summary", "content", "kb_id")
    autocomplete_fields = ("tags",)
    filter_horizontal = ()
    readonly_fields = ("kb_id", "views", "created_at", "updated_at", "site_link")
    date_hierarchy = "created_at"
    inlines = [OutgoingRelationInline, IncomingRelationInline]
    fieldsets = (
        (None, {"fields": ("title", "original_title", "slug", "entity_type", "year",
                           "is_published")}),
        ("Содержание", {"fields": ("summary", "content")}),
        ("Классификация", {"fields": ("genres", "tags", "metadata_json")}),
        ("Служебное", {"classes": ("collapse",),
                       "fields": ("kb_id", "site_link", "views", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("entity_type")
                .annotate(_out=Count("outgoing", distinct=True),
                          _in=Count("incoming", distinct=True)))

    @admin.display(description="Тип", ordering="entity_type__order")
    def type_badge(self, obj):
        return _badge(obj.entity_type)

    @admin.display(description="Связей")
    def relations_count(self, obj):
        return obj._out + obj._in

    @admin.display(description="На сайте")
    def site_link(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{}" target="_blank">Открыть карточку ↗</a>',
                           obj.get_absolute_url())


@admin.register(Relation)
class RelationAdmin(admin.ModelAdmin):
    list_display = ("source", "relation_type", "target", "weight", "note")
    list_filter = ("relation_type", "source__entity_type", "target__entity_type")
    search_fields = ("source__title", "target__title", "note")
    autocomplete_fields = ("source", "target", "relation_type")
    list_select_related = ("source__entity_type", "target__entity_type", "relation_type")
