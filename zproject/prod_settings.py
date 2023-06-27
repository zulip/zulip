from typing import Any, Dict, Tuple

from .config import get_secret

################################################################
## Zulip Server settings.
##
## This file controls settings that affect the whole Zulip server.
## See our documentation at:
##   https://zulip.readthedocs.io/en/latest/production/settings.html
##
## For developer documentation on the Zulip settings system, see:
##   https://zulip.readthedocs.io/en/latest/subsystems/settings.html
##
## Remember to restart the server after making changes here!
##   su zulip -c /home/zulip/deployments/current/scripts/restart-server


################
## Mandatory settings.
##
## These settings MUST be set in production. In a development environment,
## sensible default values will be used.

## The email address for the person or team who maintains the Zulip
## installation. Note that this is a public-facing email address; it may
## appear on 404 pages, is used as the sender's address for many automated
## emails, and is advertised as a support address. An email address like
## support@example.com is totally reasonable, as is admin@example.com.
## Do not put a display name; e.g. "support@example.com", not
## "Zulip Support <support@example.com>".
ZULIP_ADMINISTRATOR = "zulip-admin@example.com"

## The user-accessible Zulip hostname for this installation, e.g.
## zulip.example.com.  This should match what users will put in their
## web browser.  If you want to allow multiple hostnames, add the rest
## to ALLOWED_HOSTS.
##
## If you need to access the server on a specific port, you should set
## EXTERNAL_HOST to e.g. zulip.example.com:1234 here.
EXTERNAL_HOST = "zulip.example.com"

## Alternative hostnames.  A comma-separated list of strings
## representing the host/domain names that your users can enter in
## their browsers to access Zulip.  This is a security measure; for
## details, see the Django documentation:
## https://docs.djangoproject.com/en/3.2/ref/settings/#allowed-hosts
##
## Zulip automatically adds to this list "localhost", "127.0.0.1", and
## patterns representing EXTERNAL_HOST and subdomains of it.  If you are
## accessing your server by other hostnames, list them here.
##
## Note that these should just be hostnames, without port numbers.
# ALLOWED_HOSTS = ["zulip-alias.example.com", "192.0.2.1"]

## If EXTERNAL_HOST is not a valid domain name (e.g. an IP address),
## set FAKE_EMAIL_DOMAIN below to a domain that Zulip can use when
## generating (fake) email addresses for bots, dummy users, etc.
# FAKE_EMAIL_DOMAIN = "fake-domain.example.com"


################
## Outgoing email (SMTP) settings.
##
## Zulip needs to be able to send email (that is, use SMTP) so it can
## confirm new users' email addresses and send notifications.
##
## If you don't already have an SMTP provider, free ones are available.
##
## For more details, including a list of free SMTP providers and
## advice for troubleshooting, see the Zulip documentation:
##   https://zulip.readthedocs.io/en/latest/production/email.html

## EMAIL_HOST and EMAIL_HOST_USER are generally required.  If your
## SMTP server does not require authentication, leave EMAIL_HOST_USER
## commented out.
# EMAIL_HOST = "smtp.example.com"
# EMAIL_HOST_USER = ""

## Passwords and secrets are not stored in this file.  The password
## for user EMAIL_HOST_USER goes in `/etc/zulip/zulip-secrets.conf`.
## In that file, set `email_password`.  For example:
# email_password = abcd1234

## EMAIL_USE_TLS and EMAIL_PORT are required for most SMTP providers.
# EMAIL_USE_TLS = True
# EMAIL_PORT = 587

## The noreply address to be used as the sender for certain generated
## emails.  Messages sent to this address could contain sensitive user
## data and should not be delivered anywhere.  The default is
## e.g. noreply-{token}@zulip.example.com (if EXTERNAL_HOST is
## zulip.example.com).  There are potential security issues if you set
## ADD_TOKENS_TO_NOREPLY_ADDRESS=False to remove the token; see
## https://zulip.readthedocs.io/en/latest/production/email.html for details.
# ADD_TOKENS_TO_NOREPLY_ADDRESS = True
# TOKENIZED_NOREPLY_EMAIL_ADDRESS = "noreply-{token}@example.com"
## NOREPLY_EMAIL_ADDRESS is the sender for noreply emails that don't
## contain confirmation links (where the security problem fixed by
## ADD_TOKENS_TO_NOREPLY_ADDRESS does not exist), as well as for
## confirmation emails when ADD_TOKENS_TO_NOREPLY_ADDRESS=False.
# NOREPLY_EMAIL_ADDRESS = "noreply@example.com"

## Many countries and bulk mailers require certain types of email to display
## a physical mailing address to comply with anti-spam legislation.
## Non-commercial and non-public-facing installations are unlikely to need
## this setting.
## The address should have no newlines.
# PHYSICAL_ADDRESS = ""


################
## Email gateway integration.
##
## The email gateway integration supports sending messages into Zulip
## by sending an email.
## For details, see the documentation:
##   https://zulip.readthedocs.io/en/latest/production/email-gateway.html
EMAIL_GATEWAY_PATTERN = ""

## If you are using polling, edit the IMAP settings below:
##
## The IMAP login; username here and password as email_gateway_password in
## zulip-secrets.conf.
EMAIL_GATEWAY_LOGIN = ""
## The IMAP server & port to connect to
EMAIL_GATEWAY_IMAP_SERVER = ""
EMAIL_GATEWAY_IMAP_PORT = 993
## The IMAP folder name to check for emails. All emails sent to EMAIL_GATEWAY_PATTERN above
## must be delivered to this folder
EMAIL_GATEWAY_IMAP_FOLDER = "INBOX"


################
## Authentication settings.
##
## Enable at least one of the following authentication backends.
## See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html
## for documentation on our authentication backends.
##
## The install process requires EmailAuthBackend (the default) to be
## enabled.  If you want to disable it, do so after creating the
## initial realm and user.
AUTHENTICATION_BACKENDS: Tuple[str, ...] = (
    "zproject.backends.EmailAuthBackend",  # Email and password; just requires SMTP setup
    # "zproject.backends.GoogleAuthBackend",  # Google auth, setup below
    # "zproject.backends.GitHubAuthBackend",  # GitHub auth, setup below
    # "zproject.backends.GitLabAuthBackend",  # GitLab auth, setup below
    # "zproject.backends.AzureADAuthBackend",  # Microsoft Azure Active Directory auth, setup below
    # "zproject.backends.AppleAuthBackend",  # Apple auth, setup below
    # "zproject.backends.SAMLAuthBackend",  # SAML, setup below
    "zproject.backends.ZulipLDAPAuthBackend",  # LDAP, setup below
    "zproject.backends.ZulipRemoteUserBackend",  # Local SSO, setup docs on readthedocs
    # "zproject.backends.GenericOpenIdConnectBackend",  # Generic OIDC integration, setup below
)

## LDAP integration.
##
## Zulip supports retrieving information about users via LDAP, and
## optionally using LDAP as an authentication mechanism.

import ldap
from django_auth_ldap.config import GroupOfNamesType, LDAPGroupQuery, LDAPSearch  # noqa: F401

## Connecting to the LDAP server.
##
## For detailed instructions, see the Zulip documentation:
##   https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap

## The LDAP server to connect to.  Setting this enables Zulip
## automatically fetching each new user's name from LDAP.
# AUTH_LDAP_SERVER_URI = "ldaps://ldap.example.com"

## The DN of the user to bind as (i.e., authenticate as) in order to
## query LDAP.  If unset, Zulip does an anonymous bind.
# AUTH_LDAP_BIND_DN = ""

## Passwords and secrets are not stored in this file.  The password
## corresponding to AUTH_LDAP_BIND_DN goes in `/etc/zulip/zulip-secrets.conf`.
## In that file, set `auth_ldap_bind_password`.  For example:
# auth_ldap_bind_password = abcd1234

## Mapping user info from LDAP to Zulip.
##
## For detailed instructions, see the Zulip documentation:
##   https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap

## The LDAP search query to find a given user.
##
## The arguments to `LDAPSearch` are (base DN, scope, filter).  In the
## filter, the string `%(user)s` is a Python placeholder.  The Zulip
## server will replace this with the user's Zulip username, i.e. the
## name they type into the Zulip login form.
##
## For more details and alternatives, see the documentation linked above.
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "ou=users,dc=example,dc=com", ldap.SCOPE_SUBTREE, "(uid=%(user)s)"
)

## Configuration to look up a user's LDAP data given their email address
## (for Zulip reverse mapping).  If users log in as e.g. "sam" when
## their email address is "sam@example.com", set LDAP_APPEND_DOMAIN to
## "example.com".  Otherwise, leave LDAP_APPEND_DOMAIN=None and set
## AUTH_LDAP_REVERSE_EMAIL_SEARCH and AUTH_LDAP_USERNAME_ATTR below.
# LDAP_APPEND_DOMAIN = None

## LDAP attribute to find a user's email address.
##
## Leave as None if users log in with their email addresses,
## or if using LDAP_APPEND_DOMAIN.
# LDAP_EMAIL_ATTR = None

## AUTH_LDAP_REVERSE_EMAIL_SEARCH works like AUTH_LDAP_USER_SEARCH and
## should query an LDAP user given their email address.  It and
## AUTH_LDAP_USERNAME_ATTR are required when LDAP_APPEND_DOMAIN is None.
# AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
#                                             ldap.SCOPE_SUBTREE, "(email=%(email)s)")

## AUTH_LDAP_USERNAME_ATTR should be the Zulip username attribute
## (defined in AUTH_LDAP_USER_SEARCH).
# AUTH_LDAP_USERNAME_ATTR = "uid"

## This map defines how to populate attributes of a Zulip user from LDAP.
##
## The format is `zulip_name: ldap_name`; each entry maps a Zulip
## concept (on the left) to the LDAP attribute name (on the right) your
## LDAP database uses for the same concept.
AUTH_LDAP_USER_ATTR_MAP = {
    ## full_name is required; common values include "cn" or "displayName".
    ## If names are encoded in your LDAP directory as first and last
    ## name, you can instead specify first_name and last_name, and
    ## Zulip will combine those to construct a full_name automatically.
    "full_name": "cn",
    # "first_name": "fn",
    # "last_name": "ln",
    ##
    ## Profile pictures can be pulled from the LDAP "thumbnailPhoto"/"jpegPhoto" field.
    # "avatar": "thumbnailPhoto",
    ##
    ## This line is for having Zulip to automatically deactivate users
    ## who are disabled in LDAP/Active Directory (and reactivate users who are not).
    ## See docs for usage details and precise semantics.
    # "userAccountControl": "userAccountControl",
    ## Alternatively, you can map "deactivated" to a boolean attribute
    ## that is "TRUE" for deactivated users and "FALSE" otherwise.
    # "deactivated": "nsAccountLock",
    ## Restrict access to organizations using an LDAP attribute.
    ## See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#restricting-ldap-user-access-to-specific-organizations
    # "org_membership": "department",
}

## Whether to automatically deactivate users not found in LDAP. If LDAP
## is the only authentication method, then this setting defaults to
## True.  If other authentication methods are enabled, it defaults to
## False.
# LDAP_DEACTIVATE_NON_MATCHING_USERS = True

## See: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#restricting-ldap-user-access-to-specific-organizations
# AUTH_LDAP_ADVANCED_REALM_ACCESS_CONTROL = {
#    "zulip":
#    [ # OR
#      { # AND
#          "department": "main",
#          "employeeType": "staff"
#      }
#    ]
# }

########
## Google OAuth.
##
## To set up Google authentication, you'll need to do the following:
##
## (1) Visit https://console.developers.google.com/ , navigate to
## "APIs & Services" > "Credentials", and create a "Project" which will
## correspond to your Zulip instance.
##
## (2) Go to "Oauth consent screen" and create a consent screen,
## authorizing your domain and enabling the .../auth/userinfo.email,
## .../auth/userinfo.profile and openid scopes.  If all of your users
## share a Google Workspace, you can select the "Internal" user type
## during Oauth screen creation to limit authentication via this
## backend to users within your Google Workspace organization.
##
## (3) Return to "Credentials", and select "Create credentials".
## Choose "OAuth client ID", and fill in the app name as desired
## and "Authorized redirect URIs" with a value like
##   https://zulip.example.com/complete/google/
## based on your value for EXTERNAL_HOST.
##
## (4) You should get a client ID and a client secret. Copy them.
## Use the client ID as `SOCIAL_AUTH_GOOGLE_KEY` here, and put the
## client secret in zulip-secrets.conf as `social_auth_google_secret`.
# SOCIAL_AUTH_GOOGLE_KEY = "<your client ID from Google>"

########
## GitLab OAuth.
##
## To set up GitLab authentication, you'll need to do the following:
##
## (1) Register an OAuth application with GitLab at
##       https://gitlab.com/oauth/applications
##     Or the equivalent URL on a self-hosted GitLab server.
## (2) Fill in the "Redirect URI" with a value like
##       http://zulip.example.com/complete/gitlab/
## based on your value for EXTERNAL_HOST.
## (3) For "scopes", select only "read_user", and create the application.
## (4) You'll end up on a page with the Application ID and Secret for
## your new GitLab application. Use the Application ID as
## `SOCIAL_AUTH_GITLAB_KEY` here, and put the Secret in
## zulip-secrets.conf as `social_auth_gitlab_secret`.
## (5) If you are self-hosting GitLab, provide the URL of the
## GitLab server as SOCIAL_AUTH_GITLAB_API_URL here.
# SOCIAL_AUTH_GITLAB_KEY = "<your Application ID from GitLab>"
# SOCIAL_AUTH_GITLAB_API_URL = "https://gitlab.example.com"

########
## GitHub OAuth.
##
## To set up GitHub authentication, you'll need to do the following:
##
## (1) Register an OAuth2 application with GitHub at one of:
##   https://github.com/settings/developers
##   https://github.com/organizations/ORGNAME/settings/developers
## Fill in "Callback URL" with a value like
##   https://zulip.example.com/complete/github/ as
## based on your values for EXTERNAL_HOST and SOCIAL_AUTH_SUBDOMAIN.
##
## (2) You should get a page with settings for your new application,
## showing a client ID and a client secret.  Use the client ID as
## `SOCIAL_AUTH_GITHUB_KEY` here, and put the client secret in
## zulip-secrets.conf as `social_auth_github_secret`.
# SOCIAL_AUTH_GITHUB_KEY = "<your client ID from GitHub>"

## (3) Optionally, you can configure the GitHub integration to only
## allow members of a particular GitHub team or organization to log
## into your Zulip server through GitHub authentication.  To enable
## this, set one of the two parameters below:
# SOCIAL_AUTH_GITHUB_TEAM_ID = "<your team id>"
# SOCIAL_AUTH_GITHUB_ORG_NAME = "<your org name>"

## (4) If you are serving multiple Zulip organizations on different
## subdomains, you need to set SOCIAL_AUTH_SUBDOMAIN.  You can set it
## to any subdomain on which you do not plan to host a Zulip
## organization.  The default recommendation, `auth`, is a reserved
## subdomain; if you're using this setting, the "Callback URL" should be e.g.:
##   https://auth.zulip.example.com/complete/github/
#
# SOCIAL_AUTH_SUBDOMAIN = "auth"

########
## Generic OpenID Connect (OIDC).  See also documentation here:
##
##     https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#openid-connect
##

SOCIAL_AUTH_OIDC_ENABLED_IDPS: Dict[str, Any] = {
    ## This field (example: "idp_name") may appear in URLs during
    ## authentication, but is otherwise not user-visible.
    "idp_name": {
        ## The base path to the provider's OIDC API. Zulip fetches the
        ## IdP's configuration from the discovery endpoint, which will be
        ## "{oidc_url}/.well-known/openid-configuration".
        "oidc_url": "https://example.com/api/openid",
        ## The display name, used for "Log in with <display name>" buttons.
        "display_name": "Example",
        ## Optional: URL of an icon to decorate "Log in with <display name>" buttons.
        "display_icon": None,
        ## The client_id and secret provided by your OIDC IdP. To keep
        ## settings.py free of secrets, the get_secret call below
        ## reads the secret with the specified name from zulip-secrets.conf.
        "client_id": "<your client id>",
        "secret": get_secret("social_auth_oidc_secret"),
        ## Determines whether "Log in with OIDC" will automatically
        ## register a new account if one does not already exist. By
        ## default, Zulip asks the user whether they want to create an
        ## account or try to log in again using another method.
        # "auto_signup": False,
    }
}

## For documentation on this setting, see the relevant part of
## https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#openid-connect
# SOCIAL_AUTH_OIDC_FULL_NAME_VALIDATED = True

########
## SAML authentication
##
## For SAML authentication, you will need to configure the settings
## below using information from your SAML identity provider, as
## explained in:
##
##     https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#saml
##
## You will need to modify these SAML settings:
SOCIAL_AUTH_SAML_ORG_INFO = {
    "en-US": {
        "displayname": "Example, Inc. Zulip",
        "name": "zulip",
        "url": "{}{}".format("https://", EXTERNAL_HOST),
    },
}
SOCIAL_AUTH_SAML_ENABLED_IDPS: Dict[str, Any] = {
    ## The fields are explained in detail here:
    ##     https://python-social-auth.readthedocs.io/en/latest/backends/saml.html
    "idp_name": {
        ## Configure entity_id and url according to information provided to you by your IdP:
        "entity_id": "https://idp.testshib.org/idp/shibboleth",
        "url": "https://idp.testshib.org/idp/profile/SAML2/Redirect/SSO",
        ##
        ## The part below corresponds to what's likely referred to as something like
        ## "Attribute Statements" (with Okta as your IdP) or "Attribute Mapping" (with Google Workspace).
        ## The names on the right side need to correspond to the names under which
        ## the IdP will send the user attributes. With these defaults, it's expected
        ## that the user's email will be sent with the "email" attribute name,
        ## the first name and the last name with the "first_name", "last_name" attribute names.
        "attr_user_permanent_id": "email",
        "attr_first_name": "first_name",
        "attr_last_name": "last_name",
        "attr_username": "email",
        "attr_email": "email",
        ## List of additional attributes to fetch from the SAMLResponse.
        ## These attributes will be available for synchronizing custom profile fields.
        ## in SOCIAL_AUTH_SYNC_CUSTOM_ATTRS_DICT.
        # "extra_attrs": ["title", "mobilePhone"],
        ##
        ## The "x509cert" attribute is automatically read from
        ## /etc/zulip/saml/idps/{idp_name}.crt; don't specify it here.
        ##
        ## Optionally, you can edit display_name and display_icon
        ## settings below to change the name and icon that will show on
        ## the login button.
        "display_name": "SAML",
        ##
        ## Path to a square image file containing a logo to appear at
        ## the left end of the login/register buttons for this IDP.
        ## The default of None results in a text-only button.
        # "display_icon": "/path/to/icon.png",
        ##
        ## If you want this IdP to only be enabled for authentication
        ## to certain subdomains, uncomment and edit the setting below.
        # "limit_to_subdomains": ["subdomain1", "subdomain2"],
        ##
        ## You can also limit subdomains by setting "attr_org_membership"
        ## to be a SAML attribute containing the allowed subdomains for a user.
        # "attr_org_membership": "member",
        ##
        ## Determines whether "Log in with SAML" will automatically
        ## register a new account if one does not already exist. By
        ## default, Zulip asks the user whether they want to create an
        ## account or try to log in again using another method.
        # "auto_signup": False,
    },
}

# More complete documentation of the configurable security settings
# are available in the "security" part of https://github.com/onelogin/python3-saml#settings.
SOCIAL_AUTH_SAML_SECURITY_CONFIG: Dict[str, Any] = {
    ## If you've set up the optional private and public server keys,
    ## set this to True to enable signing of SAMLRequests using the
    ## private key.
    "authnRequestsSigned": False,
    ## If you'd like the Zulip server to request that the IdP limit user identity
    ## verification to a specific set of authentication contexts, you can do this
    ## by changing the requestedAuthnContext parameter to a list of specific
    ## Authentication Context Classes that you want to include in the AuthnContext. E.g.:
    ##
    # "requestedAuthnContext": ["urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport",
    #                           "urn:oasis:names:tc:SAML:2.0:ac:classes:X509"],
    ##
    ## For details on this, see the aforementioned python3-saml documentation
    ## and https://docs.oasis-open.org/security/saml/v2.0/saml-authn-context-2.0-os.pdf
    "requestedAuthnContext": False,
}

## These SAML settings you likely won't need to modify.
SOCIAL_AUTH_SAML_SP_ENTITY_ID = "https://" + EXTERNAL_HOST
SOCIAL_AUTH_SAML_TECHNICAL_CONTACT = {
    "givenName": "Technical team",
    "emailAddress": ZULIP_ADMINISTRATOR,
}
SOCIAL_AUTH_SAML_SUPPORT_CONTACT = {
    "givenName": "Support team",
    "emailAddress": ZULIP_ADMINISTRATOR,
}

# SOCIAL_AUTH_SYNC_CUSTOM_ATTRS_DICT = {
#    "example_org": {
#        "saml": {
#            # Format: "<custom profile field name>": "<attribute name from extra_attrs above>"
#            "title": "title",
#            "phone_number": "mobilePhone",
#        }
#    }
# }

########
## Apple authentication ("Sign in with Apple").
##
## Configure the below settings by following the instructions here:
##
##     https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#sign-in-with-apple
#
# SOCIAL_AUTH_APPLE_TEAM = "<your Team ID>"
# SOCIAL_AUTH_APPLE_SERVICES_ID = "<your Services ID>"
# SOCIAL_AUTH_APPLE_APP_ID = "<your App ID>"
# SOCIAL_AUTH_APPLE_KEY = "<your Key ID>"

########
## Azure Active Directory OAuth.
##
## To set up Microsoft Azure AD authentication, you'll need to do the following:
##
## (1) Open "App registrations" at
## https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
## and click "New registration".
##
## (2) In the "Redirect URI (optional)" section, select Web as the platform
## and enter https://zulip.example.com/complete/azuread-oauth2/ as the redirect URI,
## based on your values of EXTERNAL_HOST and SOCIAL_AUTH_SUBDOMAIN.
##
## (3) After registering the app, go to "Certificates & secrets" and
## generate a new client secret. Make sure to save the generated Value.
##
## (4) Enter the application ID for the app as SOCIAL_AUTH_AZUREAD_OAUTH2_KEY below
## and the generated secret Value in zulip-secrets.conf as `social_auth_azuread_oauth2_secret`.
# SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = ""

########
## SSO via REMOTE_USER.
##
## If you are using the ZulipRemoteUserBackend authentication backend,
## and REMOTE_USER does not already include a domain, set this to your
## domain (e.g. if REMOTE_USER is "username" and the corresponding
## email address is "username@example.com", set SSO_APPEND_DOMAIN =
## "example.com"), otherwise leave this as None.
# SSO_APPEND_DOMAIN = None

## JWT authentication.
##
## JWT authentication is supported both to transparently log users
## into Zulip or to fetch users' API keys. The JWT secret key and
## algorithm must be configured here.
##
## See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#jwt
JWT_AUTH_KEYS: Dict[str, Any] = {
    # Subdomain for which this JWT configuration will apply.
    "": {
        "key": get_secret("jwt_auth_key"),
        "algorithms": ["HS256"],
    },
    "zulip": {
        # Shared secret key used to validate jwt tokens, which should be stored
        # in zulip-secrets.conf and is read by the get_secret call below.
        # The key needs to be securely, randomly generated. Note that if you're
        # using the default HS256 algorithm, per RFC 7518, the key needs
        # to have at least 256 bits of entropy.
        "key": get_secret("jwt_auth_key"),
        # Algorithm with which the JWT token are signed.
        "algorithms": ["HS256"],
    }
}

################
## Service configuration

########
## PostgreSQL configuration.
##
## To access an external PostgreSQL database you should define the host name in
## REMOTE_POSTGRES_HOST, port in REMOTE_POSTGRES_PORT, password in the secrets file in the
## property postgres_password, and the SSL connection mode in REMOTE_POSTGRES_SSLMODE
## Valid values for REMOTE_POSTGRES_SSLMODE are documented in the
## "SSL Mode Descriptions" table in
##   https://www.postgresql.org/docs/9.5/static/libpq-ssl.html
# REMOTE_POSTGRES_HOST = "dbserver.example.com"
# REMOTE_POSTGRES_PORT = "5432"
# REMOTE_POSTGRES_SSLMODE = "require"

########
## RabbitMQ configuration.
##
## By default, Zulip connects to RabbitMQ running locally on the
## machine, but Zulip also supports connecting to RabbitMQ over the
## network; to use a remote RabbitMQ instance, set RABBITMQ_HOST, and
## optionally RABBITMQ_PORT, to the hostname and port here.
# RABBITMQ_HOST = "127.0.0.1"
# RABBITMQ_PORT = 5672
## To use another RabbitMQ user than the default "zulip", set RABBITMQ_USERNAME here.
# RABBITMQ_USERNAME = "zulip"
## To access the RabbitMQ server over TLS, set this to True; this is
## generally only necessary if RabbitMQ is running on a separate,
## cloud-managed, host.
# RABBITMQ_USE_TLS = False

########
## Redis configuration.
##
## By default, Zulip connects to Redis running locally on the machine,
## but Zulip also supports connecting to Redis over the network;
## to use a remote Redis instance, set REDIS_HOST here.
# REDIS_HOST = "127.0.0.1"
## For a different Redis port set the REDIS_PORT here.
# REDIS_PORT = 6379
## If you set redis_password in zulip-secrets.conf, Zulip will use that password
## to connect to the Redis server.

########
## Memcached configuration.
##
## By default, Zulip connects to memcached running locally on the machine,
## but Zulip also supports connecting to memcached over the network;
## to use a remote Memcached instance, set MEMCACHED_LOCATION here.
## Format HOST:PORT
# MEMCACHED_LOCATION = 127.0.0.1:11211
## To authenticate to memcached, set memcached_password in zulip-secrets.conf,
## and optionally change the default username "zulip@localhost" here.
# MEMCACHED_USERNAME = "zulip@localhost"


################
## Previews.

########
## Image and URL previews.
##
## Controls whether or not Zulip will provide inline image preview when
## a link to an image is referenced in a message.  Note: this feature
## can also be disabled in a realm's organization settings.
# INLINE_IMAGE_PREVIEW = True

## Controls whether or not Zulip will provide inline previews of
## websites that are referenced in links in messages.  Note: this feature
## can also be disabled in a realm's organization settings.
# INLINE_URL_EMBED_PREVIEW = True

########
## Twitter previews.
##
## Zulip supports showing inline Tweet previews when a tweet is linked
## to in a message.  To support this, Zulip must have access to the
## Twitter API via OAuth.  To obtain the various access tokens needed
## below, you must register a new application under your Twitter
## account by doing the following:
##
## 1. Log in to http://dev.twitter.com.
## 2. In the menu under your username, click My Applications. From this page, create a new application.
## 3. Click on the application you created and click "create my access token".
## 4. Fill in the values for twitter_consumer_key, twitter_consumer_secret, twitter_access_token_key,
##    and twitter_access_token_secret in /etc/zulip/zulip-secrets.conf.


################
## Logging and error reporting.
##
## Controls whether or not error reports (tracebacks) are emailed to the
## server administrators.
# ERROR_REPORTING = True
## For frontend (JavaScript) tracebacks
# BROWSER_ERROR_REPORTING = False

## Controls the DSN used to report errors to Sentry.io
# SENTRY_DSN = "https://aaa@bbb.ingest.sentry.io/1234"
# SENTRY_FRONTEND_DSN = "https://aaa@bbb.ingest.sentry.io/1234"
## What portion of events are sampled (https://docs.sentry.io/platforms/javascript/configuration/sampling/):
# SENTRY_FRONTEND_SAMPLE_RATE = 1.0
# SENTRY_FRONTEND_TRACE_RATE = 0.1

## If True, each log message in the server logs will identify the
## Python module where it came from.  Useful for tracking down a
## mysterious log message, but a little verbose.
# LOGGING_SHOW_MODULE = False

## If True, each log message in the server logs will identify the
## process ID.  Useful for correlating logs with information from
## system-level monitoring tools.
# LOGGING_SHOW_PID = False

#################
## Animated GIF integration powered by GIPHY.  See:
## https://zulip.readthedocs.io/en/latest/production/giphy-gif-integration.html
# GIPHY_API_KEY = "<Your API key from GIPHY>"

################
## Video call integrations.
##
## Controls the Zoom video call integration.  See:
## https://zulip.readthedocs.io/en/latest/production/video-calls.html
# VIDEO_ZOOM_CLIENT_ID = "<your Zoom client ID>"

## Controls the Jitsi Meet video call integration.  By default, the
## integration uses the SaaS https://meet.jit.si server.  You can specify
## your own Jitsi Meet server, or if you'd like to disable the
## integration, set JITSI_SERVER_URL = None.
# JITSI_SERVER_URL = "https://jitsi.example.com"

## Controls the BigBlueButton video call integration.  You must also
## set big_blue_button_secret in zulip-secrets.conf.
# BIG_BLUE_BUTTON_URL = "https://bbb.example.com/bigbluebutton/"


################
## Miscellaneous settings.

## How long outgoing webhook requests time out after
# OUTGOING_WEBHOOK_TIMEOUT_SECONDS = 10

## Support for mobile push notifications.  Setting controls whether
## push notifications will be forwarded through a Zulip push
## notification bouncer server to the mobile apps.  See
## https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html
## for information on how to sign up for and configure this.
# PUSH_NOTIFICATION_BOUNCER_URL = "https://push.zulipchat.com"

## Whether to redact the content of push notifications.  This is less
## usable, but avoids sending message content over the wire.  In the
## future, we're likely to replace this with an end-to-end push
## notification encryption feature.
# PUSH_NOTIFICATION_REDACT_CONTENT = False

## Whether to submit basic usage statistics to help the Zulip core team.  Details at
##
##   https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html
##
## Defaults to True if and only if the Mobile Push Notifications Service is enabled.
# SUBMIT_USAGE_STATISTICS = True

## Whether to lightly advertise sponsoring Zulip in the gear menu.
# PROMOTE_SPONSORING_ZULIP = True

## Controls whether session cookies expire when the browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

## Session cookie expiry in seconds after the last page load
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2  # 2 weeks

## Password strength requirements; learn about configuration at
## https://zulip.readthedocs.io/en/latest/production/security-model.html.
# PASSWORD_MIN_LENGTH = 6
# PASSWORD_MIN_GUESSES = 10000

## Controls whether Zulip sends "new login" email notifications.
# SEND_LOGIN_EMAILS = True

## Controls whether or not Zulip will parse links starting with
## "file:///" as a hyperlink (useful if you have e.g. an NFS share).
ENABLE_FILE_LINKS = False

## By default, files uploaded by users and profile pictures are stored
## directly on the Zulip server.  You can configure files being instead
## stored in Amazon S3 or another scalable data store here.  See docs at:
##
##   https://zulip.readthedocs.io/en/latest/production/upload-backends.html
##
## If you change LOCAL_UPLOADS_DIR to a different path, you will also
## need to manually edit Zulip's nginx configuration to use the new
## path.  For that reason, we recommend replacing /home/zulip/uploads
## with a symlink instead of changing LOCAL_UPLOADS_DIR.
LOCAL_UPLOADS_DIR = "/home/zulip/uploads"
# S3_AUTH_UPLOADS_BUCKET = ""
# S3_AVATAR_BUCKET = ""
# S3_REGION = None
# S3_ENDPOINT_URL = None
# S3_SKIP_PROXY = True

## Maximum allowed size of uploaded files, in megabytes.  This value is
## capped at 80MB in the nginx configuration, because the file upload
## implementation doesn't use chunked uploads, and browsers may crash
## with larger uploads.
## Set MAX_FILE_UPLOAD_SIZE to 0 to disable file uploads completely
## (including hiding upload-related options from UI).
MAX_FILE_UPLOAD_SIZE = 25

## Controls whether name changes are completely disabled for this
## installation.  This is useful when you're syncing names from an
## integrated LDAP/Active Directory.
NAME_CHANGES_DISABLED = False

## Controls whether avatar changes are completely disabled for this
## installation.  This is useful when you're syncing avatars from an
## integrated LDAP/Active Directory.
AVATAR_CHANGES_DISABLED = False

## Controls whether users who have not uploaded an avatar will receive an avatar
## from gravatar.com.
ENABLE_GRAVATAR = True

## To override the default avatar image if ENABLE_GRAVATAR is False, place your
## custom default avatar image at /home/zulip/local-static/default-avatar.png
## and uncomment the following line.
# DEFAULT_AVATAR_URI = "/local-static/default-avatar.png"

## The default CAMO_URI of "/external_content/" is served by the camo
## setup in the default Zulip nginx configuration.  Setting CAMO_URI
## to "" will disable the Camo integration.
CAMO_URI = "/external_content/"

## Controls the tutorial popups for new users.
# TUTORIAL_ENABLED = True

## Controls whether Zulip will rate-limit user requests.
# RATE_LIMITING = True

## Entries in this dictionary will override Zulip's default rate
## limits. Rules which are not explicitly overridden here
## will be as default. View the current rules using:
##   /home/zulip/deployments/current/scripts/get-django-setting RATE_LIMITING_RULES
##
## The limits are tuples of a number of seconds and a number of
## requests allowed over that many seconds. If multiple tuples are
## given in a rule, a request breaching any of them will trigger a
## rate-limited response to the client. For example, to change the
## limits for total API requests by each user to be at most 100
## requests per minute, and at most 200 requests per hour, add:
##   "api_by_user": [(60, 100), (3600, 200)],
# RATE_LIMITING_RULES = {
#     "api_by_ip": [
#         (60, 100),
#     ],
# }

## Fetch TOR exit node list every hour, and group all TOR exit nodes
## together into one bucket when applying rate-limiting.
# RATE_LIMIT_TOR_TOGETHER = False

## Configuration for Terms of Service and Privacy Policy for the
## server.  If unset, Zulip will never prompt users to accept Terms of
## Service.  Users will be prompted to accept the terms during account
## registration, and during login if this value has changed.
# TERMS_OF_SERVICE_VERSION = "1.0"

## Directory containing Markdown files for the server's policies.
# POLICIES_DIRECTORY = "/etc/zulip/policies/"
