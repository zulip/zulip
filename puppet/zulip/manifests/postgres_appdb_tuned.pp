# @summary Temporary shim for postgres database server profile
class zulip::postgres_appdb_tuned {
  include zulip::profile::postgres_appdb_tuned
}
