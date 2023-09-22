class zulip::postgresql_client {
  # This may get us a more recent client than the database server is
  # configured to be, ($zulip::postgresql_common::version), but
  # they're compatible.
  package { 'postgresql-client':
    ensure => installed,
  }
}
