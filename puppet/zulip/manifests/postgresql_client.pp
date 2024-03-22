class zulip::postgresql_client {
  include zulip::postgresql_common
  package { "postgresql-client-${zulip::postgresql_common::version}":
    ensure => installed,
  }
}
