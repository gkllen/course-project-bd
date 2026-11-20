"""Просмотр словаря индекса (только чтение) — для демонстрации на защите."""
from django.contrib import admin, messages

from .indexer import rebuild_index
from .models import Posting, Term


class PostingInline(admin.TabularInline):
    model = Posting
    fields = ("entry", "field", "tf")
    readonly_fields = fields
    extra = 0
    can_delete = False
    max_num = 0


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("text", "df")
    search_fields = ("text",)
    ordering = ("-df", "text")
    readonly_fields = ("text", "df")
    inlines = [PostingInline]
    actions = ["rebuild"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Перестроить весь поисковый индекс")
    def rebuild(self, request, queryset):
        stats = rebuild_index()
        self.message_user(request, f"Индекс перестроен: {stats['documents']} документов, "
                                   f"{stats['terms']} терминов, {stats['postings']} постингов.",
                          messages.SUCCESS)
