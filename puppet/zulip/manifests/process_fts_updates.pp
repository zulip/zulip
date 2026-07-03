class zulip::process_fts_updates {
  include zulip::supervisor

  # process_fts_updates runs in the Python environment at
  # /srv/zulip-database-env (see its shebang).  On frontend machines,
  # that is the environment of the current Zulip deployment; on a
  # PostgreSQL-only machine, no Zulip deployment exists, so we build a
  # minimal environment containing just psycopg2.  This class is
  # included after zulip::app_frontend_base in every supported
  # configuration that has both, so `defined` is reliable here.
  if defined(Class['zulip::app_frontend_base']) {
    file { '/srv/zulip-database-env':
      ensure => link,
      target => '/home/zulip/deployments/current',
      before => File["${zulip::common::supervisor_conf_dir}/zulip_db.conf"],
    }
  } else {
    case $facts['os']['family'] {
      'Debian': {
        # Needed to build psycopg2
        $psycopg2_build_packages = ['build-essential', 'libpq-dev', 'python3-dev']
      }
      'RedHat': {
        # zulip::postgresql_common installs postgresql-devel, which
        # provides the pg_config needed to build psycopg2.
        $psycopg2_build_packages = ['gcc', 'python3-devel']
      }
      default: {
        fail('osfamily not supported')
      }
    }
    zulip::safepackage { $psycopg2_build_packages: ensure => installed }

    file { '/srv/zulip-database-env':
      ensure  => directory,
      owner   => 'zulip',
      group   => 'zulip',
      require => User['zulip'],
    }
    ['pyproject.toml', 'uv.lock'].each |String $project_file| {
      file { "/srv/zulip-database-env/${project_file}":
        ensure => file,
        owner  => 'zulip',
        group  => 'zulip',
        mode   => '0644',
        source => "${facts['zulip_scripts_path']}/../${project_file}",
      }
    }
    exec { 'process_fts_updates_venv':
      command     => 'uv sync --frozen --no-managed-python --only-group=database',
      unless      => 'uv sync --frozen --no-managed-python --only-group=database --check',
      cwd         => '/srv/zulip-database-env',
      user        => 'zulip',
      environment => ['HOME=/home/zulip'],
      timeout     => 600,
      require     => [
        Package[$psycopg2_build_packages],
        File['/srv/zulip-database-env/pyproject.toml'],
        File['/srv/zulip-database-env/uv.lock'],
      ],
      before      => File["${zulip::common::supervisor_conf_dir}/zulip_db.conf"],
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
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/zulip_db.conf',
    notify  => Service[$zulip::common::supervisor_service],
  }
}
