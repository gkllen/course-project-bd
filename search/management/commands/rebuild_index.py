from django.core.management.base import BaseCommand

from search.indexer import rebuild_index


class Command(BaseCommand):
    help = "Полностью перестроить инвертированный поисковый индекс (BM25F)."

    def handle(self, *args, **options):
        stats = rebuild_index(verbose=options["verbosity"] > 1)
        self.stdout.write(self.style.SUCCESS(
            f"Индекс перестроен: документов {stats['documents']}, "
            f"терминов {stats['terms']}, постингов {stats['postings']}."))
