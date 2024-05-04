class zulip::postgresql_client {
  $version = zulipconf('postgresql', 'version', undef)
  if $version != undef {
    package { "postgresql-client-${version}":
      ensure => installed,
    }
  } else {
    package { 'postgresql-client':
      ensure => installed,
    }
  }
}
