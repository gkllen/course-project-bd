from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from knowledge.models import KnowledgeEntry


class PageTests(TestCase):
    """Сквозные тесты HTML-страниц на полном наборе данных seed_kb."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_kb", verbosity=0, stdout=StringIO())

    def get(self, url, status=200):
        r = self.client.get(url, HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, status, url)
        return r.content.decode()

    def test_seed_volume(self):
        counts = {code: KnowledgeEntry.objects.filter(entity_type__code=code).count()
                  for code in ("film", "character", "actor", "technique")}
        self.assertGreaterEqual(counts["film"], 8)
        self.assertGreaterEqual(counts["character"], 10)
        self.assertGreaterEqual(counts["actor"], 8)
        self.assertGreaterEqual(counts["technique"], 6)

    def test_home(self):
        body = self.get("/")
        self.assertIn("семантических связей", body)
        self.assertIn("Популярные материалы", body)

    def test_search_page(self):
        body = self.get("/search/?q=джентльменов&type=film")
        self.assertIn("<mark>", body)
        self.assertIn("Как посчитан скор", body)
        self.assertIn("1 результат ", body)

    def test_search_facets_and_bad_params(self):
        self.get("/search/?type=film&decade=2010&genre=боевик&sort=oldest")
        self.get("/search/?page=abc&year_from=x")

    def test_entry_page(self):
        body = self.get("/entry/the-gentlemen/")
        self.assertIn("Связанные сущности базы знаний", body)
        self.assertIn("Мэттью Макконахи", body)
        self.assertIn("10.5555/gr-kb.film.2019", body)
        self.assertIn("ноября", body)  # русская локаль дат

    def test_entry_views_counter(self):
        before = KnowledgeEntry.objects.get(slug="snatch").views
        self.get("/entry/snatch/")
        self.assertEqual(KnowledgeEntry.objects.get(slug="snatch").views, before + 1)

    def test_graph_and_404(self):
        self.get("/graph/")
        self.get("/graph/?focus=snatch&depth=2")
        self.get("/entry/does-not-exist/", status=404)

    def test_film_card_shows_people(self):
        body = self.get("/search/?q=Большой куш&type=film")
        self.assertIn("режиссёр", body)
