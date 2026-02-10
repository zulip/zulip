import uri_template
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CASCADE
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.lib.types import RealmPlaygroundDict
from zerver.models.linkifiers import url_template_validator
from zerver.models.realms import Realm


class RealmPlayground(models.Model):
    """Server side storage model to store playground information needed by our
    'view code in playground' feature in code blocks.
    """

    MAX_PYGMENTS_LANGUAGE_LENGTH = 40

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    url_template = models.TextField(validators=[url_template_validator])

    # User-visible display name used when configuring playgrounds in the settings page and
    # when displaying them in the playground links popover.
    name = models.TextField(db_index=True)

    # This stores the pygments lexer subclass names and not the aliases themselves.
    pygments_language = models.CharField(
        db_index=True,
        max_length=MAX_PYGMENTS_LANGUAGE_LENGTH,
        # We validate to see if this conforms to the character set allowed for a
        # language in the code block.
        validators=[
            RegexValidator(
                regex=r"^[ a-zA-Z0-9_+-./#]*$", message=_("Invalid characters in pygments language")
            )
        ],
    )

    class Meta:
        unique_together = (("realm", "pygments_language", "name"),)

    @override
    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.pygments_language} {self.name}"

    @override
    def clean(self) -> None:
        """Validate whether the URL template is valid for the playground,
        ensuring that "code" is the sole variable present in it.

        Django's `full_clean` calls `clean_fields` followed by `clean` method
        and stores all ValidationErrors from all stages to return as JSON.
        """

        # Do not continue the check if the url template is invalid to begin
        # with. The ValidationError for invalid template will only be raised by
        # the validator set on the url_template field instead of here to avoid
        # duplicates.
        if not uri_template.validate(self.url_template):
            return

        # Extract variables used in the URL template.
        template_variables = set(uri_template.URITemplate(self.url_template).variable_names)

        if "code" not in template_variables:
            raise ValidationError(_('Missing the required variable "code" in the URL template'))

        # The URL template should only contain a single variable, which is "code".
        if len(template_variables) != 1:
            raise ValidationError(
                _('"code" should be the only variable present in the URL template'),
            )


def get_realm_playgrounds(realm: Realm) -> list[RealmPlaygroundDict]:
    return [
        RealmPlaygroundDict(
            id=playground.id,
            name=playground.name,
            pygments_language=playground.pygments_language,
            url_template=playground.url_template,
        )
        for playground in RealmPlayground.objects.filter(realm=realm).all()
    ]
