* [`GET /server_settings`](/api/get-server-settings): Requests for a
  deactivated organization now return an HTTP 404 error with the
  `REALM_DEACTIVATED` error code, instead of the organization's
  settings. If the organization was deactivated after moving to a new
  URL or server, the error instead has the new `REALM_MOVED` error
  code, and a `moved_to_url` field with the organization's new URL.
