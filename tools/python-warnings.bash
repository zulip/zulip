# shellcheck shell=bash

export PYTHONWARNINGS=error

PYTHONWARNINGS+=',ignore::ResourceWarning'

# https://github.com/disqus/django-bitfield/pull/135
PYTHONWARNINGS+=',default:Attribute s is deprecated and will be removed in Python 3.14; use value instead:DeprecationWarning:__main__'

# https://github.com/boto/botocore/pull/3239
PYTHONWARNINGS+=',ignore:datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.:DeprecationWarning:botocore.auth'

# https://github.com/mahmoud/glom/pull/258
PYTHONWARNINGS+=',ignore:invalid escape sequence '\'\\' '\'':DeprecationWarning'
PYTHONWARNINGS+=',ignore:invalid escape sequence '\'\\' '\'':SyntaxWarning'

# This gets triggered due to our do_patch_activate_script
PYTHONWARNINGS+=',default:Attempting to work in a virtualenv.:UserWarning:IPython.core.interactiveshell'

# https://github.com/SAML-Toolkits/python3-saml/pull/420
PYTHONWARNINGS+=',ignore:datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version.:DeprecationWarning:onelogin.saml2.utils'
PYTHONWARNINGS+=',ignore:datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.:DeprecationWarning:onelogin.saml2.utils'

# https://github.com/python-openapi/openapi-core/issues/931
PYTHONWARNINGS+=',ignore::DeprecationWarning:openapi_core.validation.request.validators'

# https://github.com/seb-m/pyinotify/issues/204
PYTHONWARNINGS+=',ignore:The asyncore module is deprecated and will be removed in Python 3.12.:DeprecationWarning:pyinotify'

# Semgrep still supports Python 3.8
PYTHONWARNINGS+=',ignore:path is deprecated.:DeprecationWarning:semgrep.semgrep_core'

# https://github.com/scrapy/scrapy/issues/3288
PYTHONWARNINGS+=',ignore:Passing method to twisted.internet.ssl.CertificateOptions was deprecated in Twisted 17.1.0.:DeprecationWarning:scrapy.core.downloader.contextfactory'

# https://github.com/scrapy/scrapy/issues/6859
PYTHONWARNINGS+=',ignore:Attempting to mutate a Context after a Connection was created.:DeprecationWarning:scrapy.core.downloader.contextfactory'

# https://github.com/adamchainz/time-machine/pull/486
PYTHONWARNINGS+=',ignore:datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.:DeprecationWarning:time_machine'

export SQLALCHEMY_WARN_20=1
