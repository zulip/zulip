class zulip::common {
  # Common parameters
  case $facts['os']['family'] {
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

  $total_memory_bytes = $facts['memory']['system']['total_bytes']
  $total_memory_mb = $total_memory_bytes / 1024 / 1024

  $goarch = $facts['os']['architecture'] ? {
    'amd64'   => 'amd64',
    'aarch64' => 'arm64',
  }

  $versions = {
    # https://github.com/cactus/go-camo/releases
    'go-camo' => {
      'version'   => '2.6.1',
      'goversion' => '1234',
      'sha256'    => {
        'amd64'   => '25cf8aba4506c3fca02aba2f86c1c8f88be06798f129ce4a5d121b2f3801979e',
        'aarch64' => 'e9f6815c21846baf90d0d9db6038119c968634b5fd8b4806e362176b4aa832a2',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.24.0',
      'sha256'  => {
        'amd64'   => 'dea9ca38a0b852a74e81c26134671af7c0fbe65d81b0dc1c5bfe22cf7d4c8858',
        'aarch64' => 'c3fa6d16ffa261091a5617145553c71d21435ce547e44cc6dfb7470865527cc7',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => 'bffe947fa6f682884d48592ff7e9ed13bb7941a4',
      # Source code, so arch-invariant sha256
      'sha256'  => 'f1fb51b6b10e106fb269025c51c7c1ac8d9c5359cdcc4d94277f1bd254b09924',
    },

    # https://github.com/tus/tusd/releases
    # Keep in sync with tools/setup/install-tusd
    'tusd' => {
      'version' => '2.6.0',
      'sha256'  => {
        'amd64'   => '8616b1985a7494da91b019972ad8f7be5a2238f802eed7d097917af20e6f8186',
        'aarch64' => '474c46502c19fb633b9fa4e518e4dfcce9f445b119663757332a9485b525b599',
      },
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '3.0.5',
      'sha256'  => {
        'amd64'   => '367ee2863f5f46fde8ab89ce289ca3a43fab3117f8d580029c502b0462580846',  # The ubuntu-22.04 version
        'aarch64' => 'b09cb8955518520d48289a8dd6ac91322b6e41ff484a87e151a4317dff7054c2',  # There is only an ubuntu-20.04 version
      },
    },

    ### kandra packages

    # https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html
    'aws_signing_helper' => {
      'version' => '1.4.0',
      'sha256'  => {
        'amd64'   => '4166504134ffd368023b50a2c6f960d22e9be06ad4b4d03ecd9e647bf9d9a17b',
        'aarch64' => '37d0ba5f8fecae8922424625541aaef38697ed44c20f729f4be62af7c0c0d324',
      },
    },

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.42.1',
      'sha256'  => {
        'amd64'   => 'b9d7e2471e7860323f77c6417b6e402c49deacba0f961429a1b95dd245fb9607',
        'aarch64' => '672fe1d63d6ebbf4b8c59c43e1b75869367378f05088843cf6641562a8c446e2',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '11.5.2',
      'sha256'  => {
        'amd64'   => '205b16da72842143a6fa1849126b7bd74b5d12a609387d3d037fb104440ea349',
        'aarch64' => 'f87b23b02b89feba93e2d020ad5e1b420c8ac0d3ff6ff57b6818fcf3781da50a',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.9.0',
      'sha256'  => {
        'amd64'   => 'e7b65ea30eec77180487d518081d3dcb121b975f6d95f1866dfb9156c5b24075',
        'aarch64' => '5314fae1efff19abf807cfc8bd7dadbd47a35565c1043c236ffb0689dc15ef4f',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.16.0',
      'sha256'  => {
        'amd64'   => '5763bd10108e9739e7857377deeb43d2addf07c4c4f4d4c882a08847c15bfd61',
        'aarch64' => 'd88c7d663e4d6a914bca71d2c4a684225e2336c20c62cdce215b2970d2a49b72',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => '0024e4842054d5c043a0a9c8122e367338f8974c',
      'sha256'  => '9f9122711b332605080e9cfef42326b34ea4360f8246d12a097c5cfc01e3a580',
    },

    # https://github.com/ncabatoff/process-exporter/releases
    'process_exporter' => {
      'version' => '0.8.5',
      'sha256'  => {
        'amd64'   => '30b20325adc4542cf1a3bba85c1135921b7a07b39061bcab298a498b4737aeda',
        'aarch64' => '8792c2453c52c521846caca382acb940b96e0c09777fee349dae340ac66362ad',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.53.3',
      'sha256'  => {
        'amd64'   => 'ebe549477a699c464a0cef0d8d55c0cc9972a1b301fc910b5f260cfc3e08f6a3',
        'aarch64' => '36d72895b6369c1b6ee51e897f903edc2a9f41d1bee82c5d517f3179276d3cdc',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.67.0',
      'sha256'  => {
        'amd64'   => '32c5ac73b128f1463e311e639b061704fb8b84c9469d0bfef4ee4a2d920457cd',
        'aarch64' => '5ca41ca7e64aa3976bc51a6042b422260dd983559c5c1fc7b13a4a91f0be7dbc',
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
      'version' => '0.44.0',
      'sha256'  => {
        'amd64'   => '77b44e7d73a1cdac019f3ff01d5d5de767e236384541bc366fdcc517a6857b0b',
        'aarch64' => '701978e5766acfcc06b8b15884ebd34f0d5b3ffdef6dc391372c853b26301c1d',
      },
    },
  }
}
