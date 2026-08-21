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

  $supervisor_output = zulipconf('application_server', 'supervisor_output', 'file')
  file { "${zulip::common::supervisor_conf_dir}/zulip_db.conf":
    ensure  => file,
    require => [Package[supervisor], Package['python3-psycopg2']],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/zulip_db.conf.erb'),
    notify  => Service[$zulip::common::supervisor_service],
  }
}
