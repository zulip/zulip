import re
from collections.abc import Callable
from typing import Any

import django_scim.constants as scim_constants
import django_scim.exceptions as scim_exceptions
import django_scim.utils as scim_utils
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.http import HttpRequest
from django.urls import resolve
from django_scim.adapters import SCIMGroup, SCIMUser
from scim2_filter_parser.attr_paths import AttrPath

from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.user_groups import (
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    create_user_group_in_database,
    do_update_user_group_name,
)
from zerver.actions.user_settings import check_change_full_name, do_change_user_delivery_email
from zerver.actions.users import do_change_user_role, do_deactivate_user
from zerver.context_processors import get_realm_from_request
from zerver.lib.email_validation import email_allowed_for_realm, validate_email_not_already_in_realm
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import RequestNotes
from zerver.lib.subdomains import get_subdomain
from zerver.lib.user_groups import (
    check_user_group_name,
    get_role_based_system_groups_dict,
    get_user_group_direct_member_ids,
)
from zerver.models import Realm, UserProfile
from zerver.models.groups import NamedUserGroup, SystemGroups
from zerver.models.realms import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
)


class ZulipSCIMUser(SCIMUser):
    """With django-scim2, the core of a project's SCIM implementation is
    this user adapter class, which defines how to translate between the
    concepts of users in the SCIM specification and the Zulip users.
    """

    id_field = "id"

    def __init__(self, obj: UserProfile, request: HttpRequest | None = None) -> None:
        # We keep the function signature from the superclass, but this actually
        # shouldn't be called with request being None.
        assert request is not None

        # self.obj is populated appropriately by django-scim2 views with
        # an instance of UserProfile - either fetched from the database
        # or constructed via UserProfile() if the request currently being
        # handled is a User creation request (POST).
        self.obj: UserProfile

        super().__init__(obj, request)
        self.subdomain = get_subdomain(request)
        self.config = settings.SCIM_CONFIG[self.subdomain]

        # These attributes are custom to this class and will be
        # populated with values in handle_replace and similar methods
        # in response to a request for the corresponding
        # UserProfile fields to change. The .save() method inspects
        # these fields an executes the requested changes.
        self._email_new_value: str | None = None
        self._is_active_new_value: bool | None = None
        self._full_name_new_value: str | None = None
        self._role_new_value: int | None = None
        self._password_set_to: str | None = None

    def is_new_user(self) -> bool:
        return not bool(self.obj.id)

    @property
    def display_name(self) -> str:
        """
        Return the displayName of the user per the SCIM spec.

        Overridden because UserProfile uses the .full_name attribute,
        while the superclass expects .first_name and .last_name.
        """
        return self.obj.full_name

    def to_dict(self) -> dict[str, Any]:
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.

        The attribute names appearing in the dict are those defined in the SCIM User Schema:
        https://datatracker.ietf.org/doc/html/rfc7643#section-4.1
        """
        if self.config["name_formatted_included"]:
            name = {
                "formatted": self.obj.full_name,
            }
        else:
            # Some clients (e.g. Okta) operate with a first_name,
            # last_name model and don't support a full name field.
            # While we strive never to do this in the project because
            # not every culture has the first/last name structure,
            # Okta's design means we have to convert our full_name
            # into a first_name/last_name pair to provide to the
            # client.  We do naive conversion with `split`.
            if " " in self.obj.full_name:
                first_name, last_name = self.obj.full_name.split(" ", 1)
            else:
                first_name, last_name = self.obj.full_name, ""
            name = {
                "givenName": first_name,
                "familyName": last_name,
            }

        return {
            "schemas": [scim_constants.SchemaURI.USER],
            "id": str(self.obj.id),
            "userName": self.obj.delivery_email,
            "name": name,
            "displayName": self.display_name,
            "active": self.obj.is_active,
            "role": UserProfile.ROLE_ID_TO_API_NAME[self.obj.role],
            # meta is a property implemented in the superclass
            # TODO: The upstream implementation uses `user_profile.date_joined`
            # as the value of the lastModified meta attribute, which is not
            # a correct simplification. We should add proper tracking
            # of this value.
            "meta": self.meta,
        }

    def from_dict(self, d: dict[str, Any]) -> None:
        """Consume a dictionary conforming to the SCIM User Schema. The
        dictionary was originally submitted as JSON by the client in
        PUT (update a user) and POST (create a new user) requests.  A
        PUT request tells us to update User attributes to match those
        passed in the dict.  A POST request tells us to create a new
        User with attributes as specified in the dict.

        The superclass implements some very basic default behavior,
        that doesn't support changing attributes via our actions.py
        functions (which update audit logs, send events, etc.) or
        doing application-specific validation.

        Thus, we've completely overridden the upstream implementation
        to store the values of the supported attributes that the
        request would like to change. Actually modifying the database
        is implemented in self.save().

        Given that SCIMUser is an adapter class, this method is meant
        to be completely overridden, and we can expect it remain the
        case that no important django-scim2 logic relies on the
        superclass's implementation of this function.
        """
        email = d.get("userName")
        assert isinstance(email, str)
        self.change_delivery_email(email)

        name_attr_dict = d.get("name", {})
        if self.config["name_formatted_included"]:
            full_name = name_attr_dict.get("formatted", "")
        else:
            # Some providers (e.g. Okta) don't provide name.formatted.
            first_name = name_attr_dict.get("givenName", "")
            last_name = name_attr_dict.get("familyName", "")
            full_name = f"{first_name} {last_name}".strip()

        if full_name:
            assert isinstance(full_name, str)
            self.change_full_name(full_name)

        if self.is_new_user() and not full_name:
            raise scim_exceptions.BadRequestError(
                "Must specify name.formatted, name.givenName or name.familyName when creating a new user"
            )

        active = d.get("active")
        if self.is_new_user() and not active:
            raise scim_exceptions.BadRequestError("New user must have active=True")

        if active is not None:
            assert isinstance(active, bool)
            self.change_is_active(active)

        role_name = d.get("role")
        if role_name:
            assert isinstance(role_name, str)
            self.change_role(role_name)

    def change_delivery_email(self, new_value: str) -> None:
        # Note that the email_allowed_for_realm check that usually
        # appears adjacent to validate_email is present in save().
        self.validate_email(new_value)
        if self.obj.delivery_email != new_value:
            self._email_new_value = new_value

    def change_full_name(self, new_value: str) -> None:
        if new_value and self.obj.full_name != new_value:
            self._full_name_new_value = new_value

    def change_is_active(self, new_value: bool) -> None:
        if new_value != self.obj.is_active:
            self._is_active_new_value = new_value

    def change_role(self, new_role_name: str) -> None:
        try:
            role = UserProfile.ROLE_API_NAME_TO_ID[new_role_name]
        except KeyError:
            raise scim_exceptions.BadRequestError(
                f"Invalid role: {new_role_name}. Valid values are: {list(UserProfile.ROLE_API_NAME_TO_ID.keys())}"
            )
        if role != self.obj.role:
            self._role_new_value = role

    def handle_replace(
        self,
        path: AttrPath | None,
        value: str | list[object] | dict[AttrPath, object],
        operation: Any,
    ) -> None:
        """
        PATCH requests specify a list of operations of types "add", "remove", "replace".
        So far we only implement "replace" as that should be sufficient.

        This method is forked from the superclass and is called to handle "replace"
        PATCH operations. Such an operation tells us to change the values
        of a User's attributes as specified. The superclass implements a very basic
        behavior in this method and is meant to be overridden, since this is an adapter class.
        """
        if not isinstance(value, dict):
            # Restructure for use in loop below. Taken from the
            # overridden upstream method.
            assert path is not None
            value = {path: value}

        assert isinstance(value, dict)
        for attr_path, val in (value or {}).items():
            if attr_path.first_path == ("userName", None, None):
                assert isinstance(val, str)
                self.change_delivery_email(val)
            elif attr_path.first_path == ("name", "formatted", None):
                # TODO: Add support name_formatted_included=False config like we do
                # for updates via PUT.
                assert isinstance(val, str)
                self.change_full_name(val)
            elif attr_path.first_path == ("active", None, None):
                assert isinstance(val, bool)
                self.change_is_active(val)
            elif attr_path.first_path == ("role", None, None):
                assert isinstance(val, str)
                self.change_role(val)
            else:
                raise scim_exceptions.NotImplementedError("Not Implemented")

        self.save()

    def save(self) -> None:
        """
        This method is called at the end of operations modifying a user,
        and is responsible for actually applying the requested changes,
        writing them to the database.
        """
        realm = RequestNotes.get_notes(self._request).realm
        assert realm is not None

        email_new_value = getattr(self, "_email_new_value", None)
        is_active_new_value = getattr(self, "_is_active_new_value", None)
        full_name_new_value = getattr(self, "_full_name_new_value", None)
        role_new_value = getattr(self, "_role_new_value", None)
        password = getattr(self, "_password_set_to", None)

        # Clean up the internal "pending change" state, now that we've
        # fetched the values:
        self._email_new_value = None
        self._is_active_new_value = None
        self._full_name_new_value = None
        self._password_set_to = None
        self._role_new_value = None

        if email_new_value is not None:
            try:
                # Note that the validate_email check that usually
                # appears adjacent to email_allowed_for_realm is
                # present in save().
                email_allowed_for_realm(email_new_value, realm)
            except DomainNotAllowedForRealmError:
                raise scim_exceptions.BadRequestError(
                    "This email domain isn't allowed in this organization."
                )
            except DisposableEmailError:  # nocoverage
                raise scim_exceptions.BadRequestError(
                    "Disposable email domains are not allowed for this realm."
                )
            except EmailContainsPlusError:  # nocoverage
                raise scim_exceptions.BadRequestError("Email address can't contain + characters.")

            try:
                validate_email_not_already_in_realm(
                    realm, email_new_value, allow_inactive_mirror_dummies=False
                )
            except ValidationError as e:
                raise ConflictError("Email address already in use: " + str(e))

        if self.is_new_user():
            assert email_new_value is not None
            assert full_name_new_value is not None
            add_initial_stream_subscriptions = True
            if (
                self.config.get("create_guests_without_streams", False)
                and role_new_value == UserProfile.ROLE_GUEST
            ):
                add_initial_stream_subscriptions = False

            self.obj = do_create_user(
                email_new_value,
                password,
                realm,
                full_name_new_value,
                role=role_new_value,
                tos_version=UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN,
                add_initial_stream_subscriptions=add_initial_stream_subscriptions,
                acting_user=None,
            )
            return

        # TODO: The below operations should ideally be executed in a single
        # atomic block to avoid failing with partial changes getting saved.
        # This can be fixed once we figure out how do_deactivate_user can be run
        # inside an atomic block.

        # We process full_name first here, since it's the only one that can fail.
        if full_name_new_value:
            check_change_full_name(self.obj, full_name_new_value, acting_user=None)

        if email_new_value is not None:
            do_change_user_delivery_email(self.obj, email_new_value, acting_user=None)

        if role_new_value is not None:
            do_change_user_role(self.obj, role_new_value, acting_user=None)

        if is_active_new_value is not None and is_active_new_value:
            do_reactivate_user(self.obj, acting_user=None)
        elif is_active_new_value is not None and not is_active_new_value:
            do_deactivate_user(self.obj, acting_user=None)

    def delete(self) -> None:
        """
        This is consistent with Okta SCIM - users don't get DELETEd, they're deactivated
        by changing their "active" attr to False.
        """
        raise scim_exceptions.BadRequestError(
            'DELETE operation not supported. Use PUT or PATCH to modify the "active" attribute instead.'
        )


def validate_group_member_ids_from_request(realm: Realm, member_ids: list[int]) -> None:
    if member_ids:
        member_ids_set = set(member_ids)
        member_realm_ids = list(
            UserProfile.objects.filter(id__in=member_ids_set)
            .distinct("realm_id")
            .values_list("realm_id", flat=True)
        )
        if len(member_realm_ids) > 1 or member_realm_ids[0] != realm.id:
            raise scim_exceptions.BadRequestError(
                "Users outside of the realm can't be removed or added to the group"
            )

        found_member_ids_set = set(
            UserProfile.objects.filter(id__in=member_ids_set).values_list("id", flat=True)
        )
        if len(member_ids_set) != len(found_member_ids_set):
            raise scim_exceptions.BadRequestError(
                f"Invalid user ids found in the request: {member_ids_set - found_member_ids_set}"
            )


def check_can_manage_group_by_scim(user_group: NamedUserGroup) -> bool:
    # Prohibit system groups.
    if user_group.is_system_group:
        return False
    return True


class ZulipSCIMGroup(SCIMGroup):
    """
    This class contains the core of the implementation of SCIM sync of Groups.
    A SCIM Group corresponds to a NamedUserGroup object in Zulip.

    This class follows the same architecture as ZulipSCIMUser, so rather than
    re-explaining the purpose of specific method overrides or small bits of
    equivalent logic, defer to checking the corresponding comments in the
    ZulipSCIMUser implementation.
    """

    id_field = "usergroup_ptr_id"

    def __init__(self, obj: NamedUserGroup, request: HttpRequest | None = None) -> None:
        assert request is not None
        self.obj: NamedUserGroup

        super().__init__(obj, request)

        self.subdomain = get_subdomain(request)
        self.config = settings.SCIM_CONFIG[self.subdomain]

        realm = get_realm_from_request(request)
        assert realm is not None
        self.realm: Realm = realm

        self._name_new_value: str | None = None

        # The (_member_ids_to_add, _member_ids_to_remove) pair and _intended_member_ids
        # are mutually exclusive. A PUT request or PATCH request with the "replace"
        # operation to update a group will specify the
        # full set of member ids that should belong to the group, thus setting
        # _intended_member_ids.
        # A PATCH request can specify "add" and/or "remove" operations, which will
        # set _member_ids_to_add and/or _member_ids_to_remove.
        #
        # Hypothetically, a PATCH request could specify all of "add", "remove"
        # and "replace" operations at once, in any order. We do not support
        # such a mix for now, and it's not something commonly used by SCIM clients,
        # if at all.
        # If necessary, this isn't too hard to implement however, and can be done
        # by sequencing thunks for each of the operations in the PATCH request,
        # to be executed in the .save() method, instead of this current approach.
        self._member_ids_to_add: set[int] | None = None
        self._member_ids_to_remove: set[int] | None = None
        self._intended_member_ids: set[int] | None = None

    @property
    def display_name(self) -> str:
        return self.obj.name

    @property
    def members(self) -> list[dict[str, object]]:
        """
        Return a list of user dicts (ready for serialization) for the members
        of the group.

        Overridden from the superclass to use our method for fetching group
        members.
        """
        users = UserProfile.objects.filter(
            id__in=get_user_group_direct_member_ids(self.obj), is_bot=False, realm=self.realm
        ).order_by("id")
        scim_users: list[SCIMUser] = [
            scim_utils.get_user_adapter()(user, self.request) for user in users
        ]

        dicts = []
        for user in scim_users:
            d = {
                "value": user.id,
                "$ref": user.location,
                "display": user.display_name,
                "type": "User",
            }
            dicts.append(d)

        return dicts

    def is_new_group(self) -> bool:
        return not bool(self.obj.id)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.obj.id),
            "schemas": [scim_constants.SchemaURI.GROUP],
            "displayName": self.display_name,
            # Groups in the process of being created don't have members.
            "members": self.members if not self.is_new_group() else [],
            "meta": self.meta,
        }

    def from_dict(self, d: dict[str, Any]) -> None:
        name = d.get("displayName")
        if name is not None:
            assert isinstance(name, str)
            self.change_group_name(name)

        members = d.get("members")
        if members:
            self._intended_member_ids = {int(member_dict["value"]) for member_dict in members}

    def change_group_name(self, new_value: str) -> None:
        if new_value and self.obj.name != new_value:
            self._name_new_value = new_value

    def delete(self) -> None:
        if not check_can_manage_group_by_scim(self.obj):
            raise scim_exceptions.BadRequestError(
                f"Group {self.obj.name} can't be managed by SCIM."
            )

        # TODO: We don't currently support DELETE requests for groups. The correct way to handle
        # a DELETE would be to deactivate the group - but Zulip currently disallows deactivation
        # of groups under certain conditions, such as "the group is used for a permission".
        #
        # To be able to process a DELETE request, we need to implement a function to forcibly
        # deactivate a group, by correctly untangling it from all dependencies such as permissions
        # or supergroups.
        # See https://github.com/zulip/zulip/pull/34605 for current status of this work.
        raise scim_exceptions.NotImplementedError

    def save(self) -> None:
        realm = self.realm
        assert realm is not None

        if not check_can_manage_group_by_scim(self.obj):
            raise scim_exceptions.BadRequestError(
                f"Group {self.obj.name} can't be managed by SCIM."
            )

        name_new_value = getattr(self, "_name_new_value", None)
        intended_member_ids = getattr(self, "_intended_member_ids", None)
        member_ids_to_remove = getattr(self, "_member_ids_to_remove", None)
        member_ids_to_add = getattr(self, "_member_ids_to_add", None)

        # Reset the state of pending changes.
        self._name_new_value = None
        self._intended_member_ids = None
        self._member_ids_to_remove = None
        self._member_ids_to_add = None

        if name_new_value is not None:
            try:
                check_user_group_name(name_new_value)
            except JsonableError as e:
                raise scim_exceptions.BadRequestError(e.msg)
            if NamedUserGroup.objects.filter(
                name=name_new_value, realm_for_sharding=realm
            ).exists():
                raise ConflictError("Group name already in use: " + name_new_value)

        # At most one of the three should be set for a .save() call. If the SCIM request has multiple operations
        # on group memberships to run (e.g. "add" some users and "remove" some users),
        # .save() is called sequentially, processing one operation at a time.
        assert (
            sum(
                value is not None
                for value in [intended_member_ids, member_ids_to_remove, member_ids_to_add]
            )
            <= 1
        )
        if intended_member_ids is not None:
            validate_group_member_ids_from_request(realm, intended_member_ids)
        elif member_ids_to_remove is not None:
            validate_group_member_ids_from_request(realm, member_ids_to_remove)
        elif member_ids_to_add is not None:
            validate_group_member_ids_from_request(realm, member_ids_to_add)

        if self.is_new_group():
            if intended_member_ids is not None:
                members = list(UserProfile.objects.filter(id__in=intended_member_ids, realm=realm))
            else:
                members = []

            system_groups_name_dict = get_role_based_system_groups_dict(realm)
            group_nobody = system_groups_name_dict[SystemGroups.NOBODY].usergroup_ptr
            group_settings_map = dict(
                can_add_members_group=group_nobody,
                can_manage_group=group_nobody,
            )
            assert name_new_value is not None
            self.obj = create_user_group_in_database(
                name_new_value,
                members,
                realm,
                description="Created from SCIM",
                group_settings_map=group_settings_map,
                acting_user=None,
            )
            return

        with transaction.atomic(savepoint=False):
            # We need to lock the group now to conduct update operations without race conditions.
            user_group = NamedUserGroup.objects.select_for_update().get(id=self.obj.id)
            current_member_ids = set(get_user_group_direct_member_ids(user_group))
            if name_new_value is not None:
                do_update_user_group_name(self.obj, name_new_value, acting_user=None)
            if intended_member_ids is not None:
                current_member_ids = set(get_user_group_direct_member_ids(user_group))
                member_ids_to_remove = current_member_ids - intended_member_ids
                member_ids_to_add = intended_member_ids - current_member_ids

            if member_ids_to_remove:
                # Clear out ids of users who have already been removed from the group.
                member_ids_to_remove = member_ids_to_remove.intersection(current_member_ids)
                bulk_remove_members_from_user_groups(
                    [user_group], list(member_ids_to_remove), acting_user=None
                )
            if member_ids_to_add:
                # Clear out ids of users who are already in the group.
                member_ids_to_add = member_ids_to_add - current_member_ids
                bulk_add_members_to_user_groups(
                    [user_group], list(member_ids_to_add), acting_user=None
                )

    def handle_replace(
        self,
        path: AttrPath,
        value: str | list[Any] | dict[AttrPath, Any],
        operation: Any,
    ) -> None:
        if not isinstance(value, dict):
            value = {path: value}

        assert isinstance(value, dict)
        for attr_path, val in value.items():
            if attr_path.first_path == ("displayName", None, None):
                name = val
                assert isinstance(name, str)
                self.change_group_name(name)
            elif attr_path.first_path == ("members", None, None):
                intended_member_ids = {int(user_dict["value"]) for user_dict in val}
                self._intended_member_ids = intended_member_ids
            elif attr_path.first_path == ("id", None, None):
                # the "id", if present in the request, should just match the id
                # of the group - so this is a sanity check.
                assert int(val) == self.obj.id
            else:  # nocoverage
                raise scim_exceptions.NotImplementedError

        self.save()

    def handle_add(
        self,
        path: AttrPath,
        value: str | list[Any] | dict[AttrPath, Any],
        operation: Any,
    ) -> None:
        assert path is not None
        if path.first_path == ("members", None, None):
            members = value or []
            assert isinstance(members, list)
            self._member_ids_to_add = {int(member.get("value")) for member in members}
        else:  # nocoverage
            raise scim_exceptions.NotImplementedError

        self.save()

    def handle_remove(
        self,
        path: AttrPath,
        value: str | list[Any] | dict[AttrPath, Any],
        operation: Any,
    ) -> None:
        assert path is not None

        if path.is_complex:
            # django-scim2 does not support handling of complex paths and thus we generally
            # don't support them either - as they're not used by our supported SCIM clients.
            # The exception is Okta requests to remove a user from a group.
            # Rather than a PATCH request with a simple path of the form
            # { ..., "path": "members", "value": [{"value": "<user id>"}] }
            # Okta sends a request specifying the user to remove in a complex path:
            # { ..., "path": 'members[value eq "<user id>"]' }
            #
            # We don't attempt to implement general handling of complex paths. Instead,
            # we just add a hacky approach for detecting and handling this single, specific
            # kind of request.
            #
            # HACK: Detect the strange filter query formed by django-scim2 when preparing
            # to parse the path in self.split_path().
            match = re.match(r'^members\[value eq "(\d+)"\] eq ""$', path.filter)
            if not match:  # nocoverage
                raise scim_exceptions.NotImplementedError

            user_profile_id = int(match.group(1))
            self._member_ids_to_remove = {user_profile_id}
        elif path.first_path == ("members", None, None):
            members = value or []
            assert isinstance(members, list)
            self._member_ids_to_remove = {int(member.get("value")) for member in members}
        else:  # nocoverage
            raise scim_exceptions.NotImplementedError

        self.save()


def get_extra_model_filter_kwargs_getter(
    model: type[models.Model],
) -> Callable[[HttpRequest, Any, Any], dict[str, object]]:
    """Registered as GET_EXTRA_MODEL_FILTER_KWARGS_GETTER in our
    SCIM configuration.

    Returns a function which generates additional kwargs
    to add to QuerySet's .filter() when fetching a UserProfile
    corresponding to the requested SCIM User from the database.

    It's *crucial* for security that we filter by realm_id (based on
    the subdomain of the request) to prevent a SCIM client authorized
    for subdomain X from being able to interact with all of the Users
    on the entire server.

    This should be extended for Groups when implementing them by
    checking the `model` parameter; because we only support
    UserProfiles, such a check is unnecessary.
    """

    def get_extra_filter_kwargs(
        request: HttpRequest, *args: Any, **kwargs: Any
    ) -> dict[str, object]:
        realm = RequestNotes.get_notes(request).realm
        assert realm is not None
        extra_kwargs: dict[str, object] = {"realm_id": realm.id}
        # We need to determine if it's /Users or /Groups being queried.
        url_name = resolve(request.path).url_name
        if url_name in ["users", "users-search"]:
            extra_kwargs.update({"is_bot": False})
        elif url_name == "groups":
            extra_kwargs.update({"deactivated": False})
        else:
            raise AssertionError

        return extra_kwargs

    return get_extra_filter_kwargs


def base_scim_location_getter(request: HttpRequest, *args: Any, **kwargs: Any) -> str:
    """Used as the base url for constructing the Location of a SCIM resource.

    Since SCIM synchronization is scoped to an individual realm, we
    need these locations to be namespaced within the realm's domain
    namespace, which is conveniently accessed via realm.url.
    """

    realm = RequestNotes.get_notes(request).realm
    assert realm is not None

    return realm.url


class ConflictError(scim_exceptions.IntegrityError):
    """
    Per https://datatracker.ietf.org/doc/html/rfc7644#section-3.3

    If the service provider determines that the creation of the requested
    resource conflicts with existing resources (e.g., a "User" resource
    with a duplicate "userName"), the service provider MUST return HTTP
    status code 409 (Conflict) with a "scimType" error code of
    "uniqueness"

    scim_exceptions.IntegrityError class omits to include the scimType.
    """

    scim_type = "uniqueness"
