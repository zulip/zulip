Login without password is not supported. Please check the following:

* You are running under production environment. In this case, `DevAuthBackend`
  will not be supported.
* You have not added `DevAuthBackend` in `AUTHENTICATION_BACKENDS` in
  `{{ settings_path }}`.
