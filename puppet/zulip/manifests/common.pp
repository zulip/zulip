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
      'version' => '1.20.2',
      'sha256'  => {
        'amd64'   => '4eaea32f59cde4dc635fbc42161031d13e1c780b87097f4b4234cfce671f1768',
        'aarch64' => '78d632915bb75e9a6356a47a42625fd1a785c83a64a643fedd8f61e31b1b3bef',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '83ed067e342379ab9173ba4b9397bb11ec9696dc',
      # Source code, so arch-invariant sha256
      'sha256'  => '8c3ca8d9c81af81a58a743a6ea902c18d30bce58eed06037a905855669d526c4',
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
      'version' => '2.15.2',
      'sha256'  => {
        'amd64'   => '80a6fbd0b371aa14715e4fcdc0104ea9f36f249e06edac445920a0a5dc22c16a',
        'aarch64' => '8d80b70438ba496dc20dccf2c3beeff6ab43fe5e9c461f98b1141981d3058500',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '9.4.7',
      'sha256'  => {
        'amd64'   => '1e22abd627abd77c5496bc2c26bc68eb4c30aa688f7336b6a0e2c87cc80559cd',
        'aarch64' => '6b75396d5bbf46632af048af1c4d3f75e3b6a53b6fb3fef39a0b20356061a9ca',
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
      'version' => '2.43.0',
      'sha256'  => {
        'amd64'   => 'cfea92d07dfd9a9536d91dff6366d897f752b1068b9540b3e2669b0281bb8ebf',
        'aarch64' => '79c4262a27495e5dff45a2ce85495be2394d3eecd51f0366c706f6c9c729f672',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.48.0',
      'sha256'  => {
        'amd64'   => '6a65f7b27f6236f4c4fbd56b1e6138c4871b8633a145d47fff9dc9ddba63427e',
        'aarch64' => 'aa8825e33483e50b28aecddbf0439a7013ca1f762cfa41844af1074218e31793',
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
