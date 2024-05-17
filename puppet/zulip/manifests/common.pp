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
      'version'   => '2.4.11',
      'goversion' => '1222',
      'sha256'    => {
        'amd64'   => '41e21cc37bdfeef97f42a1cbf5c4730b148bd09aacaeb46d1634e8b931917853',
        'aarch64' => 'ff1e3f40abf24b92a0f9094a8e31cb499994889ab9be7e9431fa07158784e46e',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.22.2',
      'sha256'  => {
        'amd64'   => '5901c52b7a78002aeff14a21f93e0f064f74ce1360fce51c6ee68cd471216a17',
        'aarch64' => '36e720b2d564980c162a48c7e97da2e407dfcc4239e1e58d98082dfa2486a0c1',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '065ad0e4c5495caa7d0c979a7bb229da240cc3f8',
      # Source code, so arch-invariant sha256
      'sha256'  => '2ca4fb5ccc9fd9c6942eaa5b405099925e03e46ffbc711b76d72ec621d052663',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '3.0.0',
      'sha256'  => {
        'amd64'   => '430de92c8b76cade37e2f849394b761841278fb5e3a3992af3aa15c123163163',
        'aarch64' => '2223b18d62cfba32ad037ffbe515c365bd627a61f7051dd77340fc5d9e873bc6',
      },
    },

    ### kandra packages

    # https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html
    'aws_signing_helper' => {
      'version' => '1.1.1',
      'sha256'  => {
        'amd64' => '3761071497510ae1bde82aa31e34bbb63b9701deb932434e786a8479062b2b9b',
        # aarch64 would need to compile from source:
        # https://github.com/aws/rolesanywhere-credential-helper/tree/main
      },
    },

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.31.0',
      'sha256'  => {
        'amd64'   => 'baeb5b4ca0a5e500d667087f0b7fbb2865d3b8f01896cfba5144433dbe59bebd',
        'aarch64' => '2b92198d58ffd2f4551db6782b42b42ecc1ba3c7c7864f0c4ae84be940f927d3',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '10.4.2',
      'sha256'  => {
        'amd64'   => 'b12b55d4ea266fa298395c82d5f8372f544b386efab28e9d96ebc887aef37560',
        'aarch64' => '9ccd91189b540a1e8cde5028136609aa8ad4dd7332e670cb431d1e3fa28d90a4',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.7.0',
      'sha256'  => {
        'amd64'   => 'a550cd5c05f760b7934a2d0afad66d2e92e681482f5f57a917465b1fba3b02a6',
        'aarch64' => 'e386c7b53bc130eaf5e74da28efc6b444857b77df8070537be52678aefd34d96',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.15.0',
      'sha256'  => {
        'amd64'   => 'cb89fc5bf4485fb554e0d640d9684fae143a4b2d5fa443009bd29c59f9129e84',
        'aarch64' => '29ba62d538b92d39952afe12ee2e1f4401250d678ff4b354ff2752f4321c87a0',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => 'd42be2db57480b1260d997ce8358b2a8ed06b80d',
      'sha256'  => 'bd7aaa10633396ee4083e27dc370ba0ed3305057885aa1406e737bf27ec9b8a1',
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
      'version' => '2.51.1',
      'sha256'  => {
        'amd64'   => '1f933ea7515e3a6e60374ee0bfdb62bc4701c7b12c1dbafe1865c327c6e0e7d2',
        'aarch64' => 'f281f674f2e7fb726a6066585197780f63bce8455a1773ec498b5be0c8732eb5',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.58.0',
      'sha256'  => {
        'amd64'   => '6e7889e7e40c628c665c7c0e001c7f20ecefef5a254a714b748293adbb9d104e',
        'aarch64' => '4658746c9891359f4f5b369d643e120e24dcd61fb555c9742b831f1dc9d578e6',
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
      'version' => '0.37.1',
      'sha256'  => {
        'amd64'   => '5cce336aa2b4f1666148b902a1fdc2d6e7c938265315051d35cc20da11f61873',
        'aarch64' => 'ea3cad95532f30854ea013409044adbf3911ece23f1af5472958e99f122fb9f5',
      },
    },
  }
}
