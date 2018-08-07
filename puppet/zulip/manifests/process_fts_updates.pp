class zulip::process_fts_updates {
  $fts_updates_packages = [
    # Needed to run process_fts_updates
    'python3-psycopg2', # TODO: use a virtualenv instead
  ]
  zulip::safepackage { $fts_updates_packages: ensure => 'installed' }

  file { '/usr/local/bin/process_fts_updates':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/zulip/postgresql/process_fts_updates',
  }

  file { '/etc/supervisor/conf.d/zulip_db.conf':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/zulip_db.conf',
    notify  => Service[supervisor],
  }
}
