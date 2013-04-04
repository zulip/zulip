from settings import *

# South doesn't support an application migrating from having not
# having a non-default AUTH_USER_MODEL to having one because in the
# latter case it doesn't emit an auth_user table, but our migrations
# expect it to exist at the beginning and then go away (and thus will
# fail).  So we change this back to the default for running our
# initial syncdb so that we still emit an auth_user table then.
AUTH_USER_MODEL = "auth.User"
