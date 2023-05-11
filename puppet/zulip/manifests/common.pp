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
      'version' => '1.20.4',
      'sha256'  => {
        'amd64'   => '698ef3243972a51ddb4028e4a1ac63dc6d60821bf18e59a807e051fee0a385bd',
        'aarch64' => '105889992ee4b1d40c7c108555222ca70ae43fccb42e20fbf1eebb822f5e72c6',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '7c83effc9df4daf3a00a8e7215eda906693e51f6',
      # Source code, so arch-invariant sha256
      'sha256'  => '06be7595c2fb47c68c0f2e61bd760273f85d647e67b914dd1b9f4450da2e5061',
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
      'version' => '2.17.5',
      'sha256'  => {
        'amd64'   => '8200b8f0831535d5c21adfde947ca6d30930619eae36a650cbcf1005c68cd6dd',
        'aarch64' => '2071c03f870fcce6f9e82cefcff004e92f6d1af250a31d157ba921c671a5f9ec',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '9.5.2',
      'sha256'  => {
        'amd64'   => 'c58eb4d296acc4fffe5db6db5f8537ce9f11f37effe3afae27dcd05af6b93abf',
        'aarch64' => '62f3a75aca28c74e5b40226f1908393947b08f04cf3f081456ba19e889ff7f46',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.5.0',
      'sha256'  => {
        'amd64'   => 'af999fd31ab54ed3a34b9f0b10c28e9acee9ef5ac5a5d5edfdde85437db7acbb',
        'aarch64' => 'e031a539af9a619c06774788b54c23fccc2a852d41437315725a086ccdb0ed16',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.12.0',
      'sha256'  => {
        'amd64'   => 'e3301d4b8b666b870491f520c098cc4c1ce32bb5dc22ee7f40ec1914d27be891',
        'aarch64' => '60bde8f9adac2d066ba49c621a25a8d99877e3c2e2ddf9b8ba7c7188085de475',
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
      'version' => '2.43.1',
      'sha256'  => {
        'amd64'   => '8bc4d4e1021c5e538162716b8c0a624343100ea07c17643ba793a0c4ef493355',
        'aarch64' => '530d22b66dd7ffc931ca7cdac32d745b22d27c1a679c3d3da3ce22b3430864f9',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.50.0',
      'sha256'  => {
        'amd64'   => 'f634cf833ce563a38ae15fbf9d5222d671e89a0a56a8f081419aebdc0f8d0d21',
        'aarch64' => 'b696fcc332fd0e28b21ea6089e6e7abe12a8d3e7e590bf1510819d8c9113c24b',
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
