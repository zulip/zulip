from typing import TypedDict

from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models import CASCADE, Q
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.lib.cache import cache_set, cache_with_key
from zerver.models.realms import Realm


class EmojiInfo(TypedDict):
    id: str
    name: str
    source_url: str
    deactivated: bool
    author_id: int | None
    still_url: str | None


def get_all_custom_emoji_for_realm_cache_key(realm_id: int) -> str:
    return f"realm_emoji:{realm_id}"


class RealmEmoji(models.Model):
    author = models.ForeignKey(
        "UserProfile",
        blank=True,
        null=True,
        on_delete=CASCADE,
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name = models.TextField(
        validators=[
            MinLengthValidator(1),
            # The second part of the regex (negative lookbehind) disallows names
            # ending with one of the punctuation characters.
            RegexValidator(
                regex=r"^[0-9a-z.\-_]+(?<![.\-_])$",
                message=gettext_lazy("Invalid characters in emoji name"),
            ),
        ]
    )

    # The basename of the custom emoji's filename; see PATH_ID_TEMPLATE for the full path.
    file_name = models.TextField(db_index=True, null=True, blank=True)

    # Whether this custom emoji is an animated image.
    is_animated = models.BooleanField(default=False)

    deactivated = models.BooleanField(default=False)

    PATH_ID_TEMPLATE = "{realm_id}/emoji/images/{emoji_file_name}"
    STILL_PATH_ID_TEMPLATE = "{realm_id}/emoji/images/still/{emoji_filename_without_extension}.png"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "name"],
                condition=Q(deactivated=False),
                name="unique_realm_emoji_when_false_deactivated",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.id} {self.name} {self.deactivated} {self.file_name}"


def get_all_custom_emoji_for_realm_uncached(realm_id: int) -> dict[str, EmojiInfo]:
    # RealmEmoji objects with file_name=None are still in the process
    # of being uploaded, and we expect to be cleaned up by a
    # try/finally block if the upload fails, so it's correct to
    # exclude them.
    query = RealmEmoji.objects.filter(realm_id=realm_id).exclude(
        file_name=None,
    )
    d = {}
    from zerver.lib.emoji import get_emoji_url

    for realm_emoji in query.all():
        author_id = realm_emoji.author_id
        assert realm_emoji.file_name is not None
        emoji_url = get_emoji_url(realm_emoji.file_name, realm_emoji.realm_id)

        emoji_dict: EmojiInfo = dict(
            id=str(realm_emoji.id),
            name=realm_emoji.name,
            source_url=emoji_url,
            deactivated=realm_emoji.deactivated,
            author_id=author_id,
            still_url=None,
        )

        if realm_emoji.is_animated:
            # For animated emoji, we include still_url with a static
            # version of the image, so that clients can display the
            # emoji in a less distracting (not animated) fashion when
            # desired.
            emoji_dict["still_url"] = get_emoji_url(
                realm_emoji.file_name, realm_emoji.realm_id, still=True
            )

        d[str(realm_emoji.id)] = emoji_dict

    return d


@cache_with_key(get_all_custom_emoji_for_realm_cache_key, timeout=3600 * 24 * 7)
def get_all_custom_emoji_for_realm(realm_id: int) -> dict[str, EmojiInfo]:
    return get_all_custom_emoji_for_realm_uncached(realm_id)


def get_name_keyed_dict_for_active_realm_emoji(realm_id: int) -> dict[str, EmojiInfo]:
    # It's important to use the cached version here.
    realm_emojis = get_all_custom_emoji_for_realm(realm_id)
    return {row["name"]: row for row in realm_emojis.values() if not row["deactivated"]}


def flush_realm_emoji(*, instance: RealmEmoji, **kwargs: object) -> None:
    if instance.file_name is None:
        # Because we construct RealmEmoji.file_name using the ID for
        # the RealmEmoji object, it will always have file_name=None,
        # and then it'll be updated with the actual filename as soon
        # as the upload completes successfully.
        #
        # Doing nothing when file_name=None is the best option, since
        # such an object shouldn't have been cached yet, and this
        # function will be called again when file_name is set.
        return
    realm_id = instance.realm_id
    cache_set(
        get_all_custom_emoji_for_realm_cache_key(realm_id),
        get_all_custom_emoji_for_realm_uncached(realm_id),
        timeout=3600 * 24 * 7,
    )


post_save.connect(flush_realm_emoji, sender=RealmEmoji)
post_delete.connect(flush_realm_emoji, sender=RealmEmoji)
