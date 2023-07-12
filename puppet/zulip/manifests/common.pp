class zulip::common {
  # Common parameters
  case $::os['family'] {
    'Debian': {
      $nagios_plugins = 'monitoring-plugins-basic'
      $nagios_plugins_dir = '/usr/lib/nagios/plugins'
      $nginx = 'nginx-full'
      $supervisor_system_conf_dir = '/etc/supervisor/conf.d'
      $supervisor_conf_file = '/etc/supervisor/supervisord.conf'
      $supervisor_service = 'supervisor'
      $supervisor_start = '/usr/sbin/service supervisor start'
      $supervisor_reload = @(EOT)
        # The init script's timeout waiting for supervisor is shorter
        # than supervisor's timeout waiting for its programs, so we need
        # to ask supervisor to stop its programs first.
        supervisorctl stop all &&
        service supervisor restart &&
        # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=877086
        # "restart" is actually "stop" under sysvinit
        { service supervisor start || true; } &&
        service supervisor status
        | EOT
      $supervisor_status = '/usr/sbin/service supervisor status'
    }
    'RedHat': {
      $nagios_plugins = 'nagios-plugins'
      $nagios_plugins_dir = '/usr/lib64/nagios/plugins'
      $nginx = 'nginx'
      $supervisor_system_conf_dir = '/etc/supervisord.d/conf.d'
      $supervisor_conf_file = '/etc/supervisord.conf'
      $supervisor_service = 'supervisord'
      $supervisor_start = 'systemctl start supervisord'
      $supervisor_reload = 'systemctl reload supervisord'
      $supervisor_status = 'systemctl status supervisord'
    }
    default: {
      fail('osfamily not supported')
    }
  }
  $supervisor_conf_dir = "${supervisor_system_conf_dir}/zulip"

  $total_memory_bytes = $::memory['system']['total_bytes']
  $total_memory_mb = $total_memory_bytes / 1024 / 1024

  $goarch = $::os['architecture'] ? {
    'amd64'   => 'amd64',
    'aarch64' => 'arm64',
  }

  $versions = {
    # https://github.com/cactus/go-camo/releases
    'go-camo' => {
      'version'   => '2.4.3',
      'goversion' => '1195',
      'sha256'    => {
        'amd64'   => '18e096ab1e3f31df34b81c2e5c9a4435daab9985be854d7ed2166e84a8955d2e',
        'aarch64' => '85b291bb18e0ca749c8ec26bec750967f6832b346481fb61c789026b2d2d00d9',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.20.6',
      'sha256'  => {
        'amd64'   => 'b945ae2bb5db01a0fb4786afde64e6fbab50b67f6fa0eb6cfa4924f16a7ff1eb',
        'aarch64' => '4e15ab37556e979181a1a1cc60f6d796932223a0f5351d7c83768b356f84429b',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '604044bb230850769d34a83881c866e5cc1b0f59',
      # Source code, so arch-invariant sha256
      'sha256'  => '27b754963eef761be482a626627996031b2d743f6b1ec2694576682db4ef6224',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '2.0.1',
      'sha256'  => {
        'amd64'   => '2640cb9110e802bf971efdc9b7a35515af7757e06693bf5c81bd4915d8d42b9c',
        'aarch64' => '9782bd6f4f08ec26d0f2f5f8fd8f9531e4fe39f14ef5f764cbec08e93da2bbcc',
      },
    },

    ### zulip_ops packages

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.19.4',
      'sha256'  => {
        'amd64'   => 'a9fb79e44c5bae6ca8dfd2c66ac918c7e0405e3456edeb100d698961842f057f',
        'aarch64' => 'ea0021c6c69cf91c7050be105b8faa40d29c252b6d8c63d2aa33460196a41897',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '10.0.2',
      'sha256'  => {
        'amd64'   => '3249fd2a1c8998e282b8ede00cbfa680a8a3bd17ac07fe264407dfea0acea6ea',
        'aarch64' => 'c60a610e7eede1bedb651d3f2c3916a7f5e141ba813a7d6809b47c4828f04302',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.6.0',
      'sha256'  => {
        'amd64'   => '0b3573f8a7cb5b5f587df68eb28c3eb7c463f57d4b93e62c7586cb6dc481e515',
        'aarch64' => 'eb2f24626eca824c077cc7675d762bd520161c5c1a3f33c57b4b8aa0d452d613',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.13.1',
      'sha256'  => {
        'amd64'   => 'c082c59eea6469b6583c52dea9713e13e3e768c6e1aee40ff377ceea083c17ef',
        'aarch64' => 'bb0f12221a3aacd2c45bec9a0e2d5fb368a3e3b082f38db81bccf689398c3f2e',
      },
    },

    # https://github.com/ncabatoff/process-exporter/releases
    'process_exporter' => {
      'version' => '0.7.10',
      'sha256'  => {
        'amd64'   => '52503649649c0be00e74e8347c504574582b95ad428ff13172d658e82b3da1b5',
        'aarch64' => 'b377e673558bd0d51f5f771c2b3b3be44b60fcac0689709f47d8c7ca8136f6f5',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.45.0',
      'sha256'  => {
        'amd64'   => '1c7f489a3cc919c1ed0df2ae673a280309dc4a3eaa6ee3411e7d1f4bdec4d4c5',
        'aarch64' => 'eb7c3f28a83892dcd1a1c85d0ba7e1f7f9f3e7a74b567fd65a4aa2e7f8aa981a',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.51.0',
      'sha256'  => {
        'amd64'   => '46e7a17118c02c9a532938756ec209b4d2ac0eadf0a8b94b15b5ef391179522c',
        'aarch64' => '649e3103421088178b016e46cff68cc98246f78bf35e47e4473ce7fd11b0818f',
      },
    },

    # https://github.com/timonwong/uwsgi_exporter/releases
    'uwsgi_exporter' => {
      'version' => '1.3.0',
      'sha256'  => {
        'amd64'   => 'f83411b508676237bbd1b791c1bdc043a68bf914c7e48e005e2e295255f9245f',
        'aarch64' => 'ab7c9298d2fe5c5f58e3fe7c905929e93979d2b3b11c75eb8ba6ccc7a547238c',
      },
    },
  }
}
