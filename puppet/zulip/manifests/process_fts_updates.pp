class zulip::process_fts_updates {
  include zulip::supervisor
  case $facts['os']['family'] {
    'Debian': {
      $fts_updates_packages = [
        # Needed to run process_fts_updates
        'python3-psycopg2', # TODO: use a virtualenv instead
      ]
      zulip::safepackage { $fts_updates_packages: ensure => installed }
    }
    'RedHat': {
      exec {'pip_process_fts_updates':
        command => 'python3 -m pip install psycopg2',
      }
    }
    default: {
      fail('osfamily not supported')
    }
  }

  file { '/usr/local/bin/process_fts_updates':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/zulip/postgresql/process_fts_updates',
  }

  file { "${zulip::common::supervisor_conf_dir}/zulip_db.conf":
    ensure  => file,
    require => [Package[supervisor], Package['python3-psycopg2']],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/zulip_db.conf',
    notify  => Service[$zulip::common::supervisor_service],
  }
}
