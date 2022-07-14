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
      'version'   => '2.4.0',
      'goversion' => '1176',
      'sha256'    => {
        'amd64'   => '0033c412d1da09caca1774d2a7e3de3ec281e0450d67c574846f167ce253b67c',
        'aarch64' => '81bdf24e769cdf9a8bd2c5d9ecc633437eb3b22be73bdc10e03e517dd887b2b7',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.18.4',
      'sha256' => {
        'amd64'   => 'c9b099b68d93f5c5c8a8844a89f8db07eaa58270e3a1e01804f17f4cf8df02f5',
        'aarch64' => '35014d92b50d97da41dade965df7ebeb9a715da600206aa59ce1b2d05527421f',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '40870920671b64102c45b164152aef83a08d4735',
      # Source code, so arch-invariant sha256
      'sha256' => '48ec3c4eac69d2cd837e6a67fadf7215a237b3dd90cdd6cce339ce729e3ef1eb',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version'       => '2.0.0',
      'sha256'        => {
        'amd64' => 'df50c0c588fe9ff1638e42763c26e885ea32ad6dc39dee35d547186d3b94a19a',
        # aarch64 builds from source, below
      },
      # This is a Git commit hash, not a sha256sum, for when building from source.
      'git_commit_id' => '1eb88a577d5f938ffc1af9ae8f6ecdf82b7fda6b',
    },

    ### zulip_ops packages

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '9.0.3',
      'sha256' => {
        'amd64'   => '9765d30b43b121e503e2c8cce30f56b13f6ce5a9068d6a459a7667988fef4840',
        'aarch64' => 'd9dbe7727b2e6a8f0fbac9fbb2bcd8c84dc2f221663e1d819b2e7ed796f28418',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.3.1',
      'sha256' => {
        'amd64'   => '68f3802c2dd3980667e4ba65ea2e1fb03f4a4ba026cca375f15a0390ff850949',
        'aarch64' => 'f19f35175f87d41545fa7d4657e834e3a37c1fe69f3bf56bc031a256117764e7',
      },
    },

    # https://github.com/ncabatoff/process-exporter/releases
    'process_exporter' => {
      'version' => '0.7.10',
      'sha256' => {
        'amd64'   => '52503649649c0be00e74e8347c504574582b95ad428ff13172d658e82b3da1b5',
        'aarch64' => 'b377e673558bd0d51f5f771c2b3b3be44b60fcac0689709f47d8c7ca8136f6f5',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.37.0',
      'sha256' => {
        'amd64'   => 'ca70f5a261fd545da0b9893c42a73547a94ebd5111ef2b6b9f8742c5dbb73522',
        'aarch64' => '024cc048131098d408c8c3588237c42de4a13d9030b352f0a0d7f4a734fda102',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.43.0',
      'sha256' => {
        'amd64'   => '4d0d49b00ca414f667b0f347f2c231db743a952b6e596fab50fd863201d7c815',
        'aarch64' => '11c3b545a4f934799c5ed24f98fa486f490aa23ecd9735edf95ebf58ceb56273',
      },
    },

    # https://github.com/timonwong/uwsgi_exporter/releases
    'uwsgi_exporter' => {
      'version' => '1.0.0',
      'sha256' => {
        'amd64'   => '7e924dec77bca1052b4782dcf31f0c6b2ebe71d6bf4a72412b97fec45962cef0',
        'aarch64' => 'b36e26c8e94f1954c76aa9e9920be2f84ecc12b34f14a81086fedade8c48cb74',
      },
    },
  }
}
