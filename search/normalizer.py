"""
Нормализация текста для индексации и поиска.

Конвейер:
    исходный текст
      → нижний регистр, ё→е
      → токенизация (кириллица / латиница / цифры, слова через дефис)
      → лемматизация: русский — pymorphy3 (начальная форма слова),
                      латиница — стеммер Snowball (English)
      → удаление стоп-слов
      → список терминов

Одна и та же функция применяется и к документам, и к запросу, поэтому
«джентльменов», «джентльмены», «джентльмену» сводятся к термину «джентльмен».
"""
import re
from functools import lru_cache

import pymorphy3
import snowballstemmer

# Слово: буквы/цифры, допускаются внутренние дефисы и апострофы («рок-н-рольщик», «O'Neil»)
TOKEN_RE = re.compile(r"[0-9a-zа-яё]+(?:['’\-][0-9a-zа-яё]+)*", re.IGNORECASE)
CYRILLIC_RE = re.compile(r"[а-яё]")

RU_STOPWORDS = frozenset("""
а без более бы был быть в вам вас весь во вот все всего всех вы где да даже для до
его ее если есть еще же за здесь и из или им их к как ко когда кто ли либо между
меня мне может мы на над надо наш не него нее нет ни них но ну о об однако он она
они оно от очень по под после при про с со так также такой там те тем то того
тоже той только том ты у уже хотя чего чей чем что чтобы чье эта эти это этот я
который свой себя мочь один такой весь сам то-то который-то также где-то
""".split())

EN_STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or that the this to
was were will with
""".split())

_morph = None
_en_stemmer = snowballstemmer.stemmer("english")


def _analyzer():
    """Ленивая загрузка морфоанализатора (словарь ~0.4 с)."""
    global _morph
    if _morph is None:
        _morph = pymorphy3.MorphAnalyzer()
    return _morph


def tokenize(text: str):
    """Токены в исходном виде (нижний регистр, ё→е)."""
    return [m.group(0).lower().replace("ё", "е") for m in TOKEN_RE.finditer(text or "")]


# Словарь предметной области: слова, которые морфоанализатор разбирает неверно
# («кокни» он считает повелительным наклонением глагола «кокнуть»).
DOMAIN_LEXICON = {
    "кокни": "кокни",
    "ричи": "ричи",
    "куш": "куш",
    "анкл": "анкл",
}

_VOWEL_TAIL = "аяо"


def _lemmatize_oov(parses) -> str:
    """
    Лемматизация слова, отсутствующего в словаре (обычно фамилии и имена:
    «Стейтема», «Ханнэмом»). Предсказатель pymorphy3 даёт для разных падежей
    разные гипотезы, поэтому берём самую короткую нормальную форму среди
    разборов-существительных и отбрасываем «угаданную» конечную гласную
    (стейтема → стейтем). Так все падежные формы сводятся к одной основе:
        стейтем / стейтема / стейтему / стейтемом → стейтем
    """
    nouns = [p.normal_form for p in parses if p.tag.POS == "NOUN"]
    lemma = min(nouns, key=len) if nouns else parses[0].normal_form
    lemma = lemma.replace("ё", "е")
    if len(lemma) >= 5 and lemma[-1] in _VOWEL_TAIL:
        lemma = lemma[:-1]
    return lemma


@lru_cache(maxsize=200_000)
def lemmatize(token: str) -> str:
    """
    Лемма (нормальная форма) одного токена в нижнем регистре.
      • словарь предметной области → фиксированная форма;
      • словарное русское слово → нормальная форма pymorphy3;
      • несловарное русское слово (имена, фамилии) → эвристика _lemmatize_oov;
      • латиница → стеммер Snowball (English).
    """
    token = token.lower().replace("ё", "е").replace("’", "'")
    if token.isdigit():
        return token
    if token in DOMAIN_LEXICON:
        return DOMAIN_LEXICON[token]
    if CYRILLIC_RE.search(token):
        morph = _analyzer()
        parses = morph.parse(token)
        if morph.word_is_known(token):
            return parses[0].normal_form.replace("ё", "е")
        return _lemmatize_oov(parses)
    return _en_stemmer.stemWord(token.replace("'", ""))


def _is_stop(lemma: str) -> bool:
    if lemma in RU_STOPWORDS or lemma in EN_STOPWORDS:
        return True
    return len(lemma) < 2 and not lemma.isdigit()


def token_terms(token: str):
    """
    Термины для одного токена. Слово через дефис даёт и целую лемму,
    и леммы частей: «рок-н-рольщик» → [рок-н-рольщик, рок, рольщик].
    """
    terms = []
    whole = lemmatize(token)
    if not _is_stop(whole):
        terms.append(whole)
    if "-" in token:
        for part in token.split("-"):
            lemma = lemmatize(part)
            if not _is_stop(lemma) and lemma not in terms:
                terms.append(lemma)
    return terms


def normalize(text: str):
    """Текст → список терминов (с повторами, порядок сохраняется)."""
    out = []
    for tok in tokenize(text):
        out.extend(token_terms(tok))
    return out


def normalize_query(text: str):
    """Запрос → уникальные термины в порядке появления."""
    seen = []
    for term in normalize(text):
        if term not in seen:
            seen.append(term)
    return seen
