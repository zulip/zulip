* [`GET /export/realm`](/api/get-realm-exports),
  [`GET /events`](/api/get-events): Added an `export_from_prior_server`
  boolean field to the export objects returned. It is `true`
  for records that were carried across a realm import; the export
  happened on a previous server, so its tarball is no longer stored
  on this server.
* `DELETE /export/realm/{export_id}`: Export records with the
  `export_from_prior_server` field set to `true` cannot be deleted, as
  the server has no exported data to delete for them.
