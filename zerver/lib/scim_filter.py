from django.http import HttpRequest
from django_scim.filters import GroupFilterQuery, UserFilterQuery

from zerver.lib.request import RequestNotes


# This is in a separate file due to circular import issues django-scim2 runs into
# when this is placed in zerver.lib.scim.
class ZulipUserFilterQuery(UserFilterQuery):
    """This class implements the filter functionality of SCIM2.
    E.g. requests such as
    /scim/v2/Users?filter=userName eq "hamlet@zulip.com"
    can be made to refer to resources via their properties.
    This gets fairly complicated in its full scope
    (https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.2.2)
    and django-scim2 implements an entire mechanism of converting
    this SCIM2 filter syntax into SQL queries.

    What we have to do in this class is to customize django-scim2 so
    that it knows which SCIM attributes map to which UserProfile
    fields.  We can assume that get_extra_model_filter_kwargs_getter
    has already ensured that we will only interact with non-bot user
    accounts in the realm associated with this SCIM configuration.
    """

    # attr_map describes which table.column the given SCIM2 User
    # attributes refer to.
    attr_map = {
        # attr, sub attr, url
        ("userName", None, None): "zerver_userprofile.delivery_email",
        # We can only reasonably support filtering by name.formatted
        # as UserProfile.full_name is its equivalent. We don't store
        # first/last name information for UserProfile, so we can't
        # support filtering based on name.givenName or name.familyName.
        ("name", "formatted", None): "zerver_userprofile.full_name",
        ("active", None, None): "zerver_userprofile.is_active",
    }

    @classmethod
    def get_extras(cls, q: str, request: HttpRequest | None = None) -> tuple[str, list[object]]:
        """
        Return extra SQL and params to be attached to end of current Query's
        SQL and params. The return format matches the format that should be used
        for providing raw SQL with params to Django's .raw():
        https://docs.djangoproject.com/en/5.0/topics/db/sql/#passing-parameters-into-raw

        Here we ensure that results are limited to the subdomain of the request
        and also exclude bots, as we currently don't want them to be managed by SCIM2.
        """
        assert request is not None
        realm = RequestNotes.get_notes(request).realm
        assert realm is not None

        return (
            "AND zerver_userprofile.realm_id = %s AND zerver_userprofile.is_bot = False ORDER BY zerver_userprofile.id",
            [realm.id],
        )


class ZulipGroupFilterQuery(GroupFilterQuery):
    attr_map = {
        ("displayName", None, None): "zerver_namedusergroup.name",
    }

    @classmethod
    def get_extras(cls, q: str, request: HttpRequest | None = None) -> tuple[str, list[object]]:
        """
        Here we ensure that results are limited to the subdomain of the request.
        """
        assert request is not None
        realm = RequestNotes.get_notes(request).realm
        assert realm is not None

        return (
            "AND zerver_namedusergroup.realm_id = %s AND zerver_namedusergroup.deactivated = False ORDER BY zerver_namedusergroup.usergroup_ptr_id",
            [realm.id],
        )
