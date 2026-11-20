"""
Явные связи, которые не выводятся автоматически из описаний фильмов.
Формат: (источник, тип связи, цель, примечание)
"""

EXTRA_RELATIONS = [
    # --- стилистическое сходство фильмов (симметричная связь) ---
    ("lock-stock-and-two-smoking-barrels", "similar_style", "snatch", "общая «формула» ранних фильмов"),
    ("snatch", "similar_style", "rocknrolla", "ансамблевая криминальная комедия"),
    ("rocknrolla", "similar_style", "the-gentlemen", "криминальный Лондон XXI века"),
    ("lock-stock-and-two-smoking-barrels", "similar_style", "the-gentlemen", "возвращение к истокам"),
    ("the-man-from-uncle", "similar_style", "operation-fortune", "ироничный шпионский фильм"),
    ("the-man-from-uncle", "similar_style", "the-ministry-of-ungentlemanly-warfare", "стильные шпионы"),
    ("sherlock-holmes", "similar_style", "king-arthur-legend-of-the-sword", "классика в уличной эстетике"),
    ("revolver", "similar_style", "wrath-of-man", "мрачные фильмы со Стейтемом"),
    ("wrath-of-man", "similar_style", "the-covenant", "серьёзный тон без иронии"),

    # --- продолжения и отсылки ---
    ("sherlock-holmes-a-game-of-shadows", "sequel_of", "sherlock-holmes", ""),
    ("revolver", "references", "snatch", "возвращение Стейтема и криминального антуража"),
    ("king-arthur-legend-of-the-sword", "references", "east-end-london", "Лондиниум как двойник Ист-Энда"),
    ("the-gentlemen", "references", "snatch", "бокс, кокни и ансамбль бандитов"),
    ("operation-fortune", "references", "the-man-from-uncle", "шпионская команда и ирония"),

    # --- постоянные соавторы ---
    ("guy-ritchie", "collaborator", "matthew-vaughn", "продюсер ранних фильмов"),
    ("guy-ritchie", "collaborator", "jason-statham", "5 совместных фильмов"),
    ("guy-ritchie", "collaborator", "lionel-wigram", "голливудский период"),
    ("guy-ritchie", "collaborator", "christopher-benstead", "композитор с 2019 года"),
    ("guy-ritchie", "collaborator", "hugh-grant", "3 совместных фильма"),
    ("guy-ritchie", "collaborator", "madonna", "супруга (2000–2008)"),

    # --- отношения персонажей ---
    ("sherlock-holmes-character", "ally_of", "dr-watson", "напарники"),
    ("sherlock-holmes-character", "antagonist_of", "lord-blackwood", ""),
    ("sherlock-holmes-character", "antagonist_of", "professor-moriarty", "заклятый враг"),
    ("napoleon-solo", "ally_of", "illya-kuryakin", "вынужденные напарники"),
    ("mickey-pearson", "ally_of", "raymond", "босс и правая рука"),
    ("fletcher", "antagonist_of", "raymond", "шантаж"),
    ("raymond", "ally_of", "coach", "сделка"),
    ("turkish", "antagonist_of", "brick-top", "долг"),
    ("turkish", "ally_of", "mickey-oneil", "боксёр Турецкого"),
    ("mickey-oneil", "antagonist_of", "brick-top", "сорванный договорной бой"),
    ("boris-the-blade", "antagonist_of", "franky-four-fingers", "похищение бриллианта"),
    ("bullet-tooth-tony", "antagonist_of", "boris-the-blade", "охота за бриллиантом"),
    ("one-two", "ally_of", "handsome-bob", "«Дикая шайка»"),
    ("archy", "ally_of", "johnny-quid", "финал фильма"),

    # --- связи между приёмами ---
    ("nonlinear-narrative", "related_technique", "interwoven-storylines", ""),
    ("nonlinear-narrative", "related_technique", "voice-over-narrator", "рассказчик мотивирует нелинейность"),
    ("nonlinear-narrative", "related_technique", "chapter-intertitles", ""),
    ("freeze-frame-intro", "related_technique", "voice-over-narrator", "рассказчик представляет героев"),
    ("speed-ramping", "related_technique", "fight-previsualization", ""),
    ("hip-hop-montage", "related_technique", "ironic-soundtrack", "монтаж под музыку"),
    ("hip-hop-montage", "related_technique", "speed-ramping", ""),
    ("split-screen", "related_technique", "interwoven-storylines", "параллельное действие"),

    # --- темы и приёмы ---
    ("interwoven-storylines", "references", "chance-and-chaos", "совпадения связывают линии"),
    ("interwoven-storylines", "references", "macguffin", "общий объект связывает линии"),
    ("cockney-slang", "references", "east-end-london", "родина кокни"),
]
