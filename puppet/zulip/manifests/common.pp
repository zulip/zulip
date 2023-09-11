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
      'version'   => '2.4.4',
      'goversion' => '1206',
      'sha256'    => {
        'amd64'   => 'f726c6e4abfbb0c3cedf05fc0a0b440c2a8056b478d9c62780f682b5a49c6300',
        'aarch64' => 'a726820e958b827a2801c7f9f13d30757e4d2677276dbd48d998479f21ec06f2',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.21.0',
      'sha256'  => {
        'amd64'   => 'd0398903a16ba2232b389fb31032ddf57cac34efda306a0eebac34f0965a0742',
        'aarch64' => 'f3d4548edf9b22f26bbd49720350bbfe59d75b7090a1a2bff1afad8214febaf3',
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
      'version' => '2.20.6',
      'sha256'  => {
        'amd64'   => '043c1480ede8e8e093070fa705e2723b2b556763e5c10eaa020e3923fad2da20',
        'aarch64' => 'ab1d82b6eedf57527cb56d3ec2752f5ebc035e351895d966de4000f0d255a230',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '10.1.1',
      'sha256'  => {
        'amd64'   => '4b8d22ba6419a08d631ddbd543683a774f62b39e257fcda83cd1089063075ec1',
        'aarch64' => 'd5e2d468583ea8c858186d92967705dd9394add6978ceb06fa5b283e76bd7295',
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
      'version' => '2.46.0',
      'sha256'  => {
        'amd64'   => 'd2177ea21a6f60046f9510c828d4f8969628cfd35686780b3898917ef9c268b9',
        'aarch64' => 'f42513c9ef63d6bed652dfc2e986b49ebec714ed784ccaac78e20e0a2a5535bc',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.53.0',
      'sha256'  => {
        'amd64'   => '85d34fc0ecd4e602da7adf387ebe331688316071b0c2f3847dda5caa97794c48',
        'aarch64' => '57bea0a929eeaf4688d49ccfc7aa629693569639582a58ada04c17cf144626ea',
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
