import re
from typing import List, Optional, Tuple

from django.http import HttpRequest
from django_scim.filters import UserFilterQuery
from scim2_filter_parser.queries.sql import SQLQuery

from zerver.lib.request import RequestNotes

# This is in a separate file due to circular import issues django-scim2 runs into
# when this is placed in zerver.lib.scim.


class CaseInsensitiveUserNameSQLQuery(SQLQuery):
    """
    This is another ugly hack to work around the fact that per
    the RFC https://datatracker.ietf.org/doc/html/rfc7643#section-4.1.1
    the userName attribute is case insensitive, but this behavior is not
    implemented in django-scim2. userName maps to our
    zerver_userprofile.delivery_email in  SQL queries.

    We do some hacky modification of the relevant SQL to enforce
    case-insensitivity.

    Aside of the hackiness, the limitation is that this *only* works
    for the "eq" filter operator. Other filter operators of the SCIM2 protocol
    will not have the correct case-insensitive behavior - but that's okay for now,
    as the SCIM2 providers we support don't use that.

    Ideally this gets resolved upstream - https://github.com/15five/django-scim2/issues/76
    """

    def build_where_sql(self) -> None:
        super().build_where_sql()

        # self.where_sql was populated, with a string possibly containing
        # something of the form
        # zerver_userprofile.delivery_email = {a}
        # This relies on the django-scim2 implementation detail
        # that this involves always a single, lowercase ascii character, like {a}.
        # Later on in the codepath this placeholder gets appropriately replaced
        # with a value.
        pattern = r"zerver_userprofile.delivery_email = ({[a-zA-Z]})"

        # This pattern is to be found if it occurs and replaced
        # with
        # UPPER(zerver_userprofile.delivery_email) = UPPER({a})
        # which is how case-insensitive equality is ensured.
        repl = r"UPPER(zerver_userprofile.delivery_email) = UPPER(\1)"
        self.where_sql: str = re.sub(pattern, repl, self.where_sql)


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
        # attr, sub attr, uri
        ("userName", None, None): "zerver_userprofile.delivery_email",
        # We can only reasonably support filtering by name.formatted
        # as UserProfile.full_name is its equivalent. We don't store
        # first/last name information for UserProfile, so we can't
        # support filtering based on name.givenName or name.familyName.
        ("name", "formatted", None): "zerver_userprofile.full_name",
        ("active", None, None): "zerver_userprofile.is_active",
    }

    # joins tells django-scim2 to always add the specified JOINS
    # to the formed SQL queries. We need to JOIN the Realm table
    # because we need to limit the results to the realm (subdomain)
    # of the request.
    joins = ("INNER JOIN zerver_realm ON zerver_realm.id = realm_id",)

    query_class = CaseInsensitiveUserNameSQLQuery

    @classmethod
    def get_extras(cls, q: str, request: Optional[HttpRequest] = None) -> Tuple[str, List[object]]:
        """
        Return extra SQL and params to be attached to end of current Query's
        SQL and params. The return format matches the format that should be used
        for providing raw SQL with params to Django's .raw():
        https://docs.djangoproject.com/en/3.2/topics/db/sql/#passing-parameters-into-raw

        Here we ensure that results are limited to the subdomain of the request
        and also exclude bots, as we currently don't want them to be managed by SCIM2.
        """
        assert request is not None
        realm = RequestNotes.get_notes(request).realm
        assert realm is not None

        return (
            "AND zerver_realm.id = %s AND zerver_userprofile.is_bot = False ORDER BY zerver_userprofile.id",
            [realm.id],
        )
