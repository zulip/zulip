# shellcheck shell=bash

export PYTHONWARNINGS=error

PYTHONWARNINGS+=',ignore::ResourceWarning'

# https://github.com/disqus/django-bitfield/pull/135
PYTHONWARNINGS+=',default:Attribute s is deprecated and will be removed in Python 3.14; use value instead:DeprecationWarning:__main__'

# https://github.com/mahmoud/glom/pull/258
PYTHONWARNINGS+=',ignore:invalid escape sequence '\'\\' '\'':DeprecationWarning'
PYTHONWARNINGS+=',ignore:invalid escape sequence '\'\\' '\'':SyntaxWarning'
PYTHONWARNINGS+=',ignore:"\ " is an invalid escape sequence.:SyntaxWarning'

# https://github.com/ipython/ipython/pull/14876
PYTHONWARNINGS+=',ignore:'\''return'\'' in a '\''finally'\'' block:SyntaxWarning'

# https://github.com/SAML-Toolkits/python3-saml/pull/420
PYTHONWARNINGS+=',ignore:datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version.:DeprecationWarning:onelogin.saml2.utils'
PYTHONWARNINGS+=',ignore:datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.:DeprecationWarning:onelogin.saml2.utils'

# https://github.com/seb-m/pyinotify/issues/204
PYTHONWARNINGS+=',ignore:The asyncore module is deprecated and will be removed in Python 3.12.:DeprecationWarning:pyinotify'

# Semgrep still supports Python 3.8
PYTHONWARNINGS+=',ignore:path is deprecated.:DeprecationWarning:semgrep.semgrep_core'

# https://github.com/adamchainz/time-machine/pull/486
PYTHONWARNINGS+=',ignore:datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.:DeprecationWarning:time_machine'

export SQLALCHEMY_WARN_20=1
