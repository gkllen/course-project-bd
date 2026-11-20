from django.test import TestCase

from knowledge.models import EntityType, KnowledgeEntry, Relation, RelationType, Tag
from search.engine import search, suggest
from search.facets import Filters
from search.indexer import index_entry, rebuild_index
from search.models import Posting, Term
from search.normalizer import lemmatize, normalize, normalize_query
from search.snippets import make_snippet


class NormalizerTests(TestCase):
    def test_lemmatization_russian(self):
        self.assertEqual(lemmatize("джентльменов"), "джентльмен")
        self.assertEqual(lemmatize("фильмами"), "фильм")
        self.assertEqual(lemmatize("Холмса"), "холмс")

    def test_same_lemma_for_forms(self):
        forms = ["монтаж", "монтажа", "монтажом", "монтажу"]
        self.assertEqual({lemmatize(f) for f in forms}, {"монтаж"})

    def test_out_of_vocabulary_surnames(self):
        forms = ["Стейтем", "Стейтема", "Стейтему", "Стейтемом"]
        self.assertEqual({lemmatize(f) for f in forms}, {"стейтем"})
        self.assertEqual({lemmatize(f) for f in ["Пирсон", "Пирсона", "Пирсоном"]}, {"пирсон"})

    def test_domain_lexicon(self):
        self.assertEqual(lemmatize("кокни"), "кокни")

    def test_stopwords_and_punctuation(self):
        self.assertEqual(normalize("И вот, в Лондоне — снова!"), ["лондон", "снова"])

    def test_yo_and_case(self):
        self.assertEqual(normalize_query("ЁЛКА"), normalize_query("елка"))

    def test_hyphenated(self):
        terms = normalize("Рок-н-рольщик")
        self.assertIn("рок", terms)

    def test_english_stemming(self):
        self.assertEqual(normalize("Gentlemen"), normalize("gentlemen"))
        self.assertEqual(lemmatize("cards"), lemmatize("card"))


class SearchEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        film = EntityType.objects.create(code="film", name="Фильм", name_plural="Фильмы", order=1)
        tech = EntityType.objects.create(code="technique", name="Киноприём",
                                         name_plural="Киноприёмы", order=2)
        actor = EntityType.objects.create(code="actor", name="Актёр", name_plural="Актёры", order=3)
        rt = RelationType.objects.create(code="uses", name="использует приём",
                                         inverse_name="использован в")
        cls.montage_tag = Tag.objects.create(name="монтаж")
        cls.gentlemen = KnowledgeEntry.objects.create(
            title="Джентльмены", original_title="The Gentlemen", entity_type=film, year=2019,
            genres=["криминал", "комедия"],
            summary="Криминальная комедия о наркобароне Микки Пирсоне.",
            content="## Сюжет\nАмериканец продаёт марихуановую империю в Лондоне.")
        cls.snatch = KnowledgeEntry.objects.create(
            title="Большой куш", original_title="Snatch", entity_type=film, year=2000,
            genres=["криминал"],
            summary="История о краже бриллианта и подпольных боях.",
            content="## Сюжет\nДжентльмены удачи охотятся за камнем. Быстрый монтаж.")
        cls.montage = KnowledgeEntry.objects.create(
            title="Нелинейный монтаж", entity_type=tech,
            summary="Повествование, в котором события показаны не по порядку.",
            content="## Описание\nМонтаж перемешивает хронологию.")
        cls.montage.tags.add(cls.montage_tag)
        cls.statham = KnowledgeEntry.objects.create(
            title="Джейсон Стейтем", entity_type=actor, year=1967,
            summary="Британский актёр, снимавшийся в ранних фильмах Ричи.")
        KnowledgeEntry.objects.create(title="Скрытая запись", entity_type=film, year=2001,
                                      summary="Джентльмены", is_published=False)
        Relation.objects.create(source=cls.snatch, target=cls.montage, relation_type=rt)
        rebuild_index()

    def test_inflected_query_finds_entry(self):
        res = search("джентльменов")
        titles = [h.entry.title for h in res.hits]
        self.assertIn("Джентльмены", titles)
        self.assertIn("Большой куш", titles)  # слово только в content

    def test_title_weight_beats_content(self):
        res = search("джентльмены")
        self.assertEqual(res.hits[0].entry, self.gentlemen)
        self.assertGreater(res.hits[0].score, res.hits[1].score)
        self.assertIn("title", res.hits[0].explain["fields"])

    def test_unpublished_not_found(self):
        res = search("джентльмены")
        self.assertNotIn("Скрытая запись", [h.entry.title for h in res.hits])

    def test_original_title_search(self):
        res = search("snatch")
        self.assertEqual(res.hits[0].entry, self.snatch)

    def test_prefix_expansion(self):
        res = search("монта")  # незаконченное слово
        self.assertIn(self.montage, [h.entry for h in res.hits])

    def test_filters_and_disjunctive_facets(self):
        res = search("", Filters(types=["film"]))
        self.assertEqual(res.total, 2)
        counts = {f["value"]: f["count"] for f in res.facets["type"]}
        # счётчик других типов не обнуляется выбранным фильтром по типу
        self.assertEqual(counts, {"film": 2, "technique": 1, "actor": 1})
        genre = {g["value"]: g["count"] for g in res.facets["genre"]}
        self.assertEqual(genre, {"криминал": 2, "комедия": 1})

    def test_year_range(self):
        res = search("", Filters(year_from=1999, year_to=2010))
        self.assertEqual([h.entry for h in res.hits], [self.snatch])

    def test_tag_filter(self):
        res = search("", Filters(tags=[self.montage_tag.slug]))
        self.assertEqual([h.entry for h in res.hits], [self.montage])

    def test_sorting(self):
        newest = search("", Filters(types=["film"]), sort="newest")
        self.assertEqual(newest.hits[0].entry, self.gentlemen)
        oldest = search("", Filters(types=["film"]), sort="oldest")
        self.assertEqual(oldest.hits[0].entry, self.snatch)
        alpha = search("", sort="alpha")
        self.assertEqual(alpha.hits[0].entry.title, "Большой куш")

    def test_snippet_highlight_inflected(self):
        html = str(make_snippet("Там были джентльменов трое.", {"джентльмен"}))
        self.assertIn("<mark>джентльменов</mark>", html)

    def test_snippet_escapes_html(self):
        html = str(make_snippet("<script>монтаж</script>", {"монтаж"}))
        self.assertNotIn("<script>", html)

    def test_typo_suggestion(self):
        res = search("джентельмены")
        self.assertIsNotNone(res.suggestion)

    def test_suggest(self):
        self.assertEqual(suggest("джент")[0]["title"], "Джентльмены")
        self.assertEqual(suggest("sna")[0]["title"], "Большой куш")

    def test_incremental_reindex(self):
        self.statham.summary = "Исполнитель роли Турецкого."
        self.statham.save()
        index_entry(self.statham)
        self.assertTrue(Term.objects.filter(text="турецкий").exists())
        self.assertIn(self.statham, [h.entry for h in search("турецкого").hits])

    def test_signal_reindex_on_save(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.montage.summary = "Приём с флешбэками."
            self.montage.save()
        self.assertTrue(Posting.objects.filter(entry=self.montage, term__text="флешбэк").exists())

    def test_df_consistency(self):
        t = Term.objects.get(text="джентльмен")
        self.assertEqual(t.df, 2)

    def test_api(self):
        r = self.client.get("/api/search/", {"q": "джентльмены", "type": "film"},
                            HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["results"][0]["slug"], self.gentlemen.slug)
        self.assertIn("джентльмен", data["normalized_terms"])
        r = self.client.get(f"/api/entry/{self.snatch.slug}/", HTTP_HOST="127.0.0.1")
        self.assertEqual(r.json()["relations"][0]["target"]["slug"], self.montage.slug)
        r = self.client.get("/api/graph/", {"focus": self.montage.slug}, HTTP_HOST="127.0.0.1")
        self.assertEqual(len(r.json()["nodes"]), 2)
        self.assertEqual(len(r.json()["edges"]), 1)
        r = self.client.get("/api/suggest/", {"q": "джент"}, HTTP_HOST="127.0.0.1")
        self.assertEqual(r.json()["suggestions"][0]["slug"], self.gentlemen.slug)
