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
      $supervisor_start = '/etc/init.d/supervisor start'
      # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=877086
      # "restart" is actually "stop" under sysvinit
      $supervisor_reload = '/etc/init.d/supervisor restart && (/etc/init.d/supervisor start || /bin/true) && /etc/init.d/supervisor status'
      $supervisor_status = '/etc/init.d/supervisor status'
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
      'version' => '1.18.1',
      'sha256' => {
        'amd64'   => 'b3b815f47ababac13810fc6021eb73d65478e0b2db4b09d348eefad9581a2334',
        'aarch64' => '56a91851c97fb4697077abbca38860f735c32b38993ff79b088dac46e4735633',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => 'dbb816b62b790432414db7cafbb4583d5092c601',
      # Source code, so arch-invariant sha256
      'sha256' => '3c02676af074bf7c18a29343e0824cb87da4837bf7bbe2837ac81c254f813c32',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version'       => '1.1.3-rc-with-build',
      'sha256'        => {
        'amd64' => '109a80f4c019e0f1d52602e90d2a181eb844494ece2d099a149cf9204b71113e',
        # aarch64 builds from source, below
      },
      # This is a Git commit hash, not a sha256sum, for when building from source.
      'git_commit_id' => '52f990fe87679ee4651fe3fb7629a2ac799f50c6',
    },

    ### zulip_ops packages

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '8.5.0',
      'sha256' => {
        'amd64'   => 'ad5e858e2255d69da45f83f9571cf741c6867ed8ccede5ad42e90079119b98aa',
        'aarch64' => '6e906e0902b88314cd8f5a49c11140398981a7643b268dc04632fc30667581ae',
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
      'version' => '2.35.0',
      'sha256' => {
        'amd64'   => 'e4546960688d1c85530ec3a93e109d15b540f3251e1f4736d0d9735e1e857faf',
        'aarch64' => '3ebe0c533583a9ab03363a80aa629edd8e0cc42da3583e33958eb7abe74d4cd2',
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
