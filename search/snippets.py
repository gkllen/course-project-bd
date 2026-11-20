"""
Сниппеты и подсветка найденных слов.

Слово подсвечивается, если его лемма совпала с термином запроса (или начинается
с префикса незаконченного слова). Поэтому по запросу «джентльмены» подсветится
и «джентльменов», и «Джентльмены».
"""
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .normalizer import TOKEN_RE, token_terms

WINDOW = 32  # длина сниппета в словах


def _word_matches(word, terms, prefixes):
    for t in token_terms(word):
        if t in terms or any(t.startswith(p) for p in prefixes):
            return True
    return False


def highlight(text: str, terms, prefixes=()) -> str:
    """HTML-экранированный текст с <mark> вокруг совпавших слов."""
    if not text:
        return ""
    terms = set(terms)
    if not terms and not prefixes:
        return mark_safe(escape(text))
    out, pos = [], 0
    for m in TOKEN_RE.finditer(text):
        out.append(escape(text[pos:m.start()]))
        word = m.group(0)
        out.append(f"<mark>{escape(word)}</mark>" if _word_matches(word, terms, prefixes)
                   else escape(word))
        pos = m.end()
    out.append(escape(text[pos:]))
    return mark_safe("".join(out))


def make_snippet(text: str, terms, prefixes=(), window=WINDOW) -> str:
    """
    Выбрать окно из `window` слов с максимальной плотностью совпадений
    и вернуть его с подсветкой. Без совпадений — начало текста.
    """
    text = " ".join((text or "").split())
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return ""
    hits = [1 if _word_matches(m.group(0), set(terms), prefixes) else 0 for m in matches]

    best_start, best = 0, -1
    cur = sum(hits[:window])
    best, best_start = cur, 0
    for i in range(1, max(1, len(matches) - window + 1)):
        cur += hits[i + window - 1] - hits[i - 1]
        if cur > best:
            best, best_start = cur, i
    # отступаем на пару слов влево, чтобы совпадение не стояло в самом начале
    if best > 0 and best_start > 0:
        first_hit = hits.index(1, best_start)
        best_start = max(0, min(best_start, first_hit - 4))

    end_idx = min(len(matches), best_start + window) - 1
    start_char = matches[best_start].start()
    end_char = matches[end_idx].end()
    fragment = text[start_char:end_char]
    prefix = "… " if start_char > 0 else ""
    suffix = " …" if end_char < len(text) else ""
    return mark_safe(prefix + highlight(fragment, terms, prefixes) + suffix)
