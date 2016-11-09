from django.conf import settings
from django.template import Library
from django.utils.safestring import mark_safe
from django.utils.lru_cache import lru_cache

register = Library()

def and_n_others(values, limit):
    # type: (List[str], int) -> str
    # A helper for the commonly appended "and N other(s)" string, with
    # the appropriate pluralization.
    return " and %d other%s" % (len(values) - limit,
                                "" if len(values) == limit + 1 else "s")

@register.filter(name='display_list', is_safe=True)
def display_list(values, display_limit):
    # type: (List[str], int) -> str
    """
    Given a list of values, return a string nicely formatting those values,
    summarizing when you have more than `display_limit`. Eg, for a
    `display_limit` of 3 we get the following possible cases:

    Jessica
    Jessica and Waseem
    Jessica, Waseem, and Tim
    Jessica, Waseem, Tim, and 1 other
    Jessica, Waseem, Tim, and 2 others
    """
    if len(values) == 1:
        # One value, show it.
        display_string = "%s" % (values[0],)
    elif len(values) <= display_limit:
        # Fewer than `display_limit` values, show all of them.
        display_string = ", ".join(
            "%s" % (value,) for value in values[:-1])
        display_string += " and %s" % (values[-1],)
    else:
        # More than `display_limit` values, only mention a few.
        display_string = ", ".join(
            "%s" % (value,) for value in values[:display_limit])
        display_string += and_n_others(values, display_limit)

    return display_string

@lru_cache(512 if settings.PRODUCTION else 0)
@register.filter(name='render_markdown_path', is_safe=True)
def render_markdown_path(markdown_file_path):
    # type: (str) -> str
    """
    Given a path to a markdown file, return the rendered html
    """
    import markdown
    markdown_string = open(markdown_file_path).read()
    html = markdown.markdown(markdown_string, safe_mode='escape')
    return mark_safe(html)
