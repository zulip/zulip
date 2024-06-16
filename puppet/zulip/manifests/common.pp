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
      'version'   => '2.4.13',
      'goversion' => '1222',
      'sha256'    => {
        'amd64'   => '3fbe4dbd16b533eecfb68dbcd988eab185a07bd9b41b8b070287637df4d3d7b6',
        'aarch64' => 'c5a2d9664a57e172551adac4bbd96898af0c11822b74c641ea8af62c3c5c4dab',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.22.3',
      'sha256'  => {
        'amd64'   => '8920ea521bad8f6b7bc377b4824982e011c19af27df88a815e3586ea895f1b36',
        'aarch64' => '6c33e52a5b26e7aa021b94475587fce80043a727a54ceb0eee2f9fc160646434',
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
      'version' => '2.32.1',
      'sha256'  => {
        'amd64'   => '59238a42faea26e01cea3f0c9482a3bb2d1e5f200e3f9929820a11ab0eac5253',
        'aarch64' => '4ac86ade7ff15391dfb7c2f3f24a2d05a2e43097f45f5c882043905aadd6060a',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '11.0.0',
      'sha256'  => {
        'amd64'   => '97c70aa4fd11aa75bbb575d7d48764cb3a6c3356b53f34c7750c0dd7e006204d',
        'aarch64' => '24c05394013da1b35039102dd3950ae515b871920655d815d26c78c1f0f559bf',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.8.1',
      'sha256'  => {
        'amd64'   => 'fbadb376afa7c883f87f70795700a8a200f7fd45412532cc1938a24d41078011',
        'aarch64' => '3b5c4765e429d73d0ec83fcd14af39087025e1f7073422fa24be8f4fa3d3bb96',
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
      'version' => '30c04e2049aead94ff23fc4862ee187003b5de35',
      'sha256'  => 'ec45b77f7f2915b28c68678aa83e6fcdeed19b92ecff800425fb78b1b7e67bf8',
    },

    # https://github.com/ncabatoff/process-exporter/releases
    'process_exporter' => {
      'version' => '0.8.2',
      'sha256'  => {
        'amd64'   => '1fde5cc65ed9e9c27fc3b0f19afff3f5526bff3351ddc4429499e25ef75728a4',
        'aarch64' => 'af88c3d74c2db9316d30b7127f2278339303a9af923b0748f13c7c8d6cf401b5',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.52.0',
      'sha256'  => {
        'amd64'   => '7f31c5d6474bbff3e514e627e0b7a7fbbd4e5cea3f315fd0b76cad50be4c1ba3',
        'aarch64' => 'b503c0f552e381d7d3f84dfd275166bf07c74f99c428ffed69447d4ab3259901',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.59.0',
      'sha256'  => {
        'amd64'   => '7ad805a21d9423a721e6a0c48190d14b9f18a11507ee3eafbf84df11c71c3b4d',
        'aarch64' => '5b70c854fe7ec8cf9eaf32db74ca8ab8be6396f1acb61b1505439c2f93df7019',
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
      'version' => '0.38.0',
      'sha256'  => {
        'amd64'   => '86bd28eadebd55937455364f8a10aa1f4bd66154bc8fe06cb5c6e63475c081a7',
        'aarch64' => 'f06c3a403f9ad1eecf050aa6e901efe8a157f49c0a465b213f1e78eb9f8393ce',
      },
    },
  }
}
