"""Шаблонные теги портала: построение URL с фильтрами, подписи полей, проценты."""
from django import template
from django.utils.html import format_html

register = template.Library()

FIELD_LABELS = {
    "title": "Заголовок",
    "tags": "Теги",
    "summary": "Аннотация",
    "meta": "Атрибуты",
    "content": "Содержание",
}


def _params(context):
    request = context["request"]
    return request.GET.copy()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Текущий query string с заменёнными параметрами (?page=2 и т.п.)."""
    params = _params(context)
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + params.urlencode()


@register.simple_tag(takes_context=True)
def url_toggle(context, key, value):
    """Добавить значение фильтра, если его нет, или убрать, если есть. Сбрасывает страницу."""
    params = _params(context)
    value = str(value)
    values = params.getlist(key)
    if value in values:
        values.remove(value)
    else:
        values.append(value)
    params.setlist(key, values)
    params.pop("page", None)
    return "?" + params.urlencode()


@register.simple_tag(takes_context=True)
def url_without(context, *keys):
    params = _params(context)
    for key in keys:
        params.pop(key, None)
    params.pop("page", None)
    return "?" + params.urlencode()


@register.filter
def field_label(code):
    return FIELD_LABELS.get(code, code)


@register.filter
def percent(value, total):
    try:
        return max(2, min(100, round(float(value) / float(total) * 100)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def ru_plural(n, forms):
    """{{ n|ru_plural:"результат,результата,результатов" }} → «21 результат», «3 результата»."""
    one, few, many = forms.split(",")
    try:
        n = abs(int(n))
    except (TypeError, ValueError):
        return many
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def type_badge(entity_type, outline=False):
    cls = "badge badge-outline" if outline else "badge"
    return format_html('<span class="{}" style="--c:{}">{}</span>', cls, entity_type.color,
                       entity_type.name)
