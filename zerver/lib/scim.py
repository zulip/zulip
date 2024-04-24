from typing import Any, Callable, Dict, List, Optional, Type, Union

import django_scim.constants as scim_constants
import django_scim.exceptions as scim_exceptions
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest
from django_scim.adapters import SCIMUser
from scim2_filter_parser.attr_paths import AttrPath

from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.user_settings import check_change_full_name, do_change_user_delivery_email
from zerver.actions.users import do_change_user_role, do_deactivate_user
from zerver.lib.email_validation import email_allowed_for_realm, validate_email_not_already_in_realm
from zerver.lib.request import RequestNotes
from zerver.lib.subdomains import get_subdomain
from zerver.models import UserProfile
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

    ROLE_TYPE_TO_NAME = {
        UserProfile.ROLE_REALM_OWNER: "owner",
        UserProfile.ROLE_REALM_ADMINISTRATOR: "administrator",
        UserProfile.ROLE_MODERATOR: "moderator",
        UserProfile.ROLE_MEMBER: "member",
        UserProfile.ROLE_GUEST: "guest",
    }
    ROLE_NAME_TO_TYPE = {v: k for k, v in ROLE_TYPE_TO_NAME.items()}

    def __init__(self, obj: UserProfile, request: Optional[HttpRequest] = None) -> None:
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
        # in response to a request for the the corresponding
        # UserProfile fields to change. The .save() method inspects
        # these fields an executes the requested changes.
        self._email_new_value: Optional[str] = None
        self._is_active_new_value: Optional[bool] = None
        self._full_name_new_value: Optional[str] = None
        self._role_new_value: Optional[int] = None
        self._password_set_to: Optional[str] = None

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

    def to_dict(self) -> Dict[str, Any]:
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
            "id": self.obj.id,
            "userName": self.obj.delivery_email,
            "name": name,
            "displayName": self.display_name,
            "active": self.obj.is_active,
            "role": self.ROLE_TYPE_TO_NAME[self.obj.role],
            # meta is a property implemented in the superclass
            # TODO: The upstream implementation uses `user_profile.date_joined`
            # as the value of the lastModified meta attribute, which is not
            # a correct simplification. We should add proper tracking
            # of this value.
            "meta": self.meta,
        }

    def from_dict(self, d: Dict[str, Any]) -> None:
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
            role = self.ROLE_NAME_TO_TYPE[new_role_name]
        except KeyError:
            raise scim_exceptions.BadRequestError(
                f"Invalid role: {new_role_name}. Valid values are: {list(self.ROLE_NAME_TO_TYPE.keys())}"
            )
        if role != self.obj.role:
            self._role_new_value = role

    def handle_replace(
        self,
        path: Optional[AttrPath],
        value: Union[str, List[object], Dict[AttrPath, object]],
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
        for path, val in (value or {}).items():
            if path.first_path == ("userName", None, None):
                assert isinstance(val, str)
                self.change_delivery_email(val)
            elif path.first_path == ("name", "formatted", None):
                # TODO: Add support name_formatted_included=False config like we do
                # for updates via PUT.
                assert isinstance(val, str)
                self.change_full_name(val)
            elif path.first_path == ("active", None, None):
                assert isinstance(val, bool)
                self.change_is_active(val)
            elif path.first_path == ("role", None, None):
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

        if email_new_value:
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
                validate_email_not_already_in_realm(realm, email_new_value)
            except ValidationError as e:
                raise ConflictError("Email address already in use: " + str(e))

        if self.is_new_user():
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

        if email_new_value:
            do_change_user_delivery_email(self.obj, email_new_value)

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


def get_extra_model_filter_kwargs_getter(
    model: Type[models.Model],
) -> Callable[[HttpRequest, Any, Any], Dict[str, object]]:
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
    ) -> Dict[str, object]:
        realm = RequestNotes.get_notes(request).realm
        assert realm is not None
        return {"realm_id": realm.id, "is_bot": False}

    return get_extra_filter_kwargs


def base_scim_location_getter(request: HttpRequest, *args: Any, **kwargs: Any) -> str:
    """Used as the base url for constructing the Location of a SCIM resource.

    Since SCIM synchronization is scoped to an individual realm, we
    need these locations to be namespaced within the realm's domain
    namespace, which is conveniently accessed via realm.uri.
    """

    realm = RequestNotes.get_notes(request).realm
    assert realm is not None

    return realm.uri


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
