import re2
import uri_template
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.lib import cache
from zerver.lib.cache import cache_delete, cache_with_key
from zerver.lib.exceptions import MissingDependentParameterError
from zerver.lib.per_request_cache import (
    flush_per_request_cache,
    return_same_value_during_entire_request,
)
from zerver.lib.types import LinkifierDict
from zerver.models.realms import Realm


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


# A function with the same name implements this on the JS side.
# Please replicate any changes here to that function as well.
def expand_reverse_template(
    reverse_template: str, match: "re2._Match[str]", group_set: set[str]
) -> str:
    output: list[str] = []
    index = 0
    while index < len(reverse_template):
        if reverse_template.startswith("{{", index):
            output.append("{")
            index += 2
        elif reverse_template.startswith("}}", index):
            output.append("}")
            index += 2
        elif reverse_template[index] == "{":
            end_index = reverse_template.find("}", index + 1)
            if end_index == -1:
                raise ValidationError(_("Invalid auto-conversion field: missing '}' character."))
            name = reverse_template[index + 1 : end_index]
            if not name:
                raise ValidationError(_("Invalid auto-conversion field: empty field name."))
            if name not in group_set:
                raise ValidationError(
                    _(
                        "Group %(name)r in auto-conversion field is not present in linkifier pattern."
                    ),
                    params={"name": name},
                )
            output.append(match.group(name))
            index = end_index + 1
        else:
            output.append(reverse_template[index])
            index += 1
    return "".join(output)


def filter_pattern_validator(value: str) -> "re2._Regexp[str]":
    try:
        # Do not write errors to stderr (this still raises exceptions)
        options = re2.Options()
        options.log_errors = False

        regex = re2.compile(value, options=options)
    except re2.error as e:
        if len(e.args) >= 1:
            if isinstance(e.args[0], str):  # nocoverage
                raise ValidationError(_("Bad regular expression: {regex}").format(regex=e.args[0]))
            if isinstance(e.args[0], bytes):
                raise ValidationError(
                    _("Bad regular expression: {regex}").format(regex=e.args[0].decode())
                )
        raise ValidationError(_("Unknown regular expression error"))  # nocoverage

    return regex


def url_template_validator(value: str) -> None:
    """Validate as a URL template"""
    if not uri_template.validate(value):
        raise ValidationError(_("Invalid URL template."))


class RealmFilter(models.Model):
    """Realm-specific regular expressions to automatically linkify certain
    strings inside the Markdown processor.  See "Custom filters" in the settings UI.
    """

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    pattern = models.TextField()
    url_template = models.TextField(validators=[url_template_validator])
    example_input = models.TextField(blank=True, null=True)
    reverse_template = models.TextField(blank=True, null=True)
    # Linkifiers are applied in a message/topic in order; the processing order
    # is important when there are overlapping patterns.
    order = models.IntegerField(default=0)

    class Meta:
        unique_together = ("realm", "pattern")

    @override
    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.pattern} {self.url_template}"

    @override
    def clean(self) -> None:
        """Validate whether the set of parameters in the URL template
        match the set of parameters in the regular expression.

        Django's `full_clean` calls `clean_fields` followed by `clean` method
        and stores all ValidationErrors from all stages to return as JSON.
        """

        # Extract variables present in the pattern
        pattern = filter_pattern_validator(self.pattern)
        group_set = set(pattern.groupindex.keys())

        example_input = normalize_optional_text(self.example_input)
        reverse_template = normalize_optional_text(self.reverse_template)

        if reverse_template is not None and example_input is None:
            raise MissingDependentParameterError(
                required_parameter="Example text",
                set_parameter="auto-conversion field",
            )

        if example_input is not None:
            match = pattern.search(example_input)
            if match is None:
                raise ValidationError(_("Example input does not match the linkifier pattern."))
            elif reverse_template is not None:
                reversed_input = expand_reverse_template(reverse_template, match, group_set)
                if reversed_input != example_input:
                    raise ValidationError(_("Example text does not match auto-conversion field."))

        # Do not continue the check if the url template is invalid to begin with.
        # The ValidationError for invalid template will only be raised by the validator
        # set on the url_template field instead of here to avoid duplicates.
        if not uri_template.validate(self.url_template):
            return

        # Extract variables used in the URL template.
        template_variables_set = set(uri_template.URITemplate(self.url_template).variable_names)

        # Report patterns missing in linkifier pattern.
        missing_in_pattern_set = template_variables_set - group_set
        if len(missing_in_pattern_set) > 0:
            name = min(missing_in_pattern_set)
            raise ValidationError(
                _("Group %(name)r in URL template is not present in linkifier pattern."),
                params={"name": name},
            )

        missing_in_url_set = group_set - template_variables_set
        # Report patterns missing in URL template.
        if len(missing_in_url_set) > 0:
            # We just report the first missing pattern here. Users can
            # incrementally resolve errors if there are multiple
            # missing patterns.
            name = min(missing_in_url_set)
            raise ValidationError(
                _("Group %(name)r in linkifier pattern is not present in URL template."),
                params={"name": name},
            )


def get_linkifiers_cache_key(realm_id: int) -> str:
    return f"{cache.KEY_PREFIX}:all_linkifiers_for_realm:{realm_id}"


@return_same_value_during_entire_request
@cache_with_key(get_linkifiers_cache_key, timeout=3600 * 24 * 7)
def linkifiers_for_realm(realm_id: int) -> list[LinkifierDict]:
    return [
        LinkifierDict(
            pattern=linkifier.pattern,
            url_template=linkifier.url_template,
            id=linkifier.id,
            example_input=linkifier.example_input,
            reverse_template=linkifier.reverse_template,
        )
        for linkifier in RealmFilter.objects.filter(realm_id=realm_id).order_by("order")
    ]


def flush_linkifiers(*, instance: RealmFilter, **kwargs: object) -> None:
    realm_id = instance.realm_id
    cache_delete(get_linkifiers_cache_key(realm_id))
    flush_per_request_cache("linkifiers_for_realm")


post_save.connect(flush_linkifiers, sender=RealmFilter)
post_delete.connect(flush_linkifiers, sender=RealmFilter)
