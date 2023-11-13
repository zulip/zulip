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
      'version'   => '2.4.6',
      'goversion' => '1213',
      'sha256'    => {
        'amd64'   => '41a494c4d071e2cc79b5d3924e585afa2918360362bd8e85ef10de0952ce464d',
        'aarch64' => '124f9e04b67547048fbdbeaf2c939ac80caa49c2dd48f5f94cbd42f22cb137e7',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.21.3',
      'sha256'  => {
        'amd64'   => '1241381b2843fae5a9707eec1f8fb2ef94d827990582c7c7c32f5bdfbfd420c8',
        'aarch64' => 'fc90fa48ae97ba6368eecb914343590bbb61b388089510d0c56c2dde52987ef3',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => 'c86310d7000dcb9865fcd25ff3c8455c1603f7fa',
      # Source code, so arch-invariant sha256
      'sha256'  => 'db8c6c08bb0c5a88449d0cda5f361f9e6a25427d73eeaab4563b9435665e81b4',
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
      'version' => '2.21.2',
      'sha256'  => {
        'amd64'   => '0016d21b20d6b83fe10d514d10ca1dbed854e8694d71fada9749e702730ed728',
        'aarch64' => 'aa6085a9b24e349dbcef301127aebc6e8c3adfa8389964df5e91d96b3fb92e08',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '10.2.0',
      'sha256'  => {
        'amd64'   => '284d36e955b194963346a4eaaf2e21f2f9b53485c1eec254b9ccfe5bfb357a81',
        'aarch64' => 'd4e0d1507bc255994e913a5b8f55931609f0cd41919ad0966a487b0c41ec433c',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.6.1',
      'sha256'  => {
        'amd64'   => 'ecc41b3b4d53f7b9c16a370419a25a133e48c09dfc49499d63bcc0c5e0cf3d01',
        'aarch64' => 'f99ea62cec600bca5c926d300522d7a3bb797592d70dc1bcdc20b57811f1d439',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.13.2',
      'sha256'  => {
        'amd64'   => '33f820116a1c0cfc0a069d237036e05c142d216976b6fcb7c11df5abf5a537f8',
        'aarch64' => '95baed4bc22c9b369eb2b2225c2d8b543ea23e2e7f2f17a8fc2986d4b0a4df19',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => '4406fb928539e3ea994bf30c5452a8a0c9261840',
      'sha256'  => 'f40d0f65f4a9b28d56e6d9fcf1e491952c38e22fb2f77dd1db89f4ff63bad7c0',
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
      'version' => '2.47.2',
      'sha256'  => {
        'amd64'   => '6f48cd8d748cbb8e61d0cee825b63e80d8de370dc8ca19ff6eb0326f45f6e525',
        'aarch64' => 'c8d9bac223b630c3e893e0793c99b3e9d35f6d62719193060cce31cab8a30528',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.55.0',
      'sha256'  => {
        'amd64'   => '9c0012dff5c0008f07ae126a6db81789e0f93a259c99889485cef9ea33edc585',
        'aarch64' => '938b774f60b677f72108c2246ebfda23fe803f1c158ff23e049c2c2a7b52937b',
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

    # https://vector.dev/download/
    'vector' => {
      'version' => '0.34.0',
      'sha256'  => {
        'amd64'   => '3a39e712da43126262db878c3ae7647b23aac88834dea2763cc84269cb3c0206',
        'aarch64' => '57acc628c495882e2ace787ac804e7bab57e42ae322fcc4e3861cd5a106a1323',
      },
    },
  }
}
