# @summary Temporary shim for postgresql database server profile
class zulip::postgres_appdb_tuned {
  include zulip::profile::postgresql
}
