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
      'version'   => '2.5.1',
      'goversion' => '1225',
      'sha256'    => {
        'amd64'   => '6b66a926fb6f3e93db63069eef79682b540618d4976ce7e1b917f3ae3e8b986e',
        'aarch64' => 'cee9b1dc3a62efb104d8aa73d5dcee41c161cec1aeeee0f0004a76819e3a117f',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.22.5',
      'sha256'  => {
        'amd64'   => '904b924d435eaea086515bc63235b192ea441bd8c9b198c507e85009e6e4c7f0',
        'aarch64' => '8d21325bfcf431be3660527c1a39d3d9ad71535fabdf5041c826e44e31642b5a',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '85c4c64e1e01b899456d42459966a106f66c7cd5',
      # Source code, so arch-invariant sha256
      'sha256'  => 'f8cc99cb708cbd549e06099628ef286a5fdda73bb327d8c140d3014441bfefc2',
    },

    # https://github.com/tus/tusd/releases
    'tusd' => {
      'version' => '2.5.0',
      'sha256'  => {
        'amd64'   => 'f4cbdb8d228b28f46c3e7b9e29e5db262e7416f7ca1033c6c5e8186cf6c7381c',
        'aarch64' => 'b2101951789857765d64c33d672a38b5825946163aa058b208fc862867cdc405',
      },
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
      'version' => '2.36.4',
      'sha256'  => {
        'amd64'   => '22ba24c7019fc7f2ffc72307fa6a0ff5981f4254184f1e99777abc81aa4f8dde',
        'aarch64' => 'a638db3d6d7356c4ad5556d288d8a13d57530a05bc73bc5f1b3e0edc46284967',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '11.1.0',
      'sha256'  => {
        'amd64'   => '33822a0b275ea4f216c9a3bdda53d1dba668e3e9873dc52104bc565bcbd8d856',
        'aarch64' => '80b36751c29593b8fdb72906bd05f8833631dd826b8447bcdc9ba9bb0f6122aa',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.8.2',
      'sha256'  => {
        'amd64'   => '6809dd0b3ec45fd6e992c19071d6b5253aed3ead7bf0686885a51d85c6643c66',
        'aarch64' => '627382b9723c642411c33f48861134ebe893e70a63bcc8b3fc0619cd0bfac4be',
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
      'version' => '0.8.3',
      'sha256'  => {
        'amd64'   => '249db36771a4e66eaacca0ce31294de200df30eaf59a190c46639b98c5815969',
        'aarch64' => 'dc40582d4779d8df8356cad56b130a7c909c4df07d62e7852fa5d5cb6d12ee50',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.53.1',
      'sha256'  => {
        'amd64'   => '2234aa0f66d9f9b854144f6faaaed72a316df7a680d9dad7cb48e49a6fa5332c',
        'aarch64' => 'a7f28c83c3c943b953a9d00860bd3f2422464fb7c27a3c4037ef1ce2a41592b5',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.62.0',
      'sha256'  => {
        'amd64'   => 'a09f92a6b366e37c654e50522c7b80e4a625396b2499fd42cf17e1aa91e56d5e',
        'aarch64' => 'da7a75ed4a3fe5c01ebb6192a2172b85b79dd7c06cb6e69aa927362454c69788',
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
      'version' => '0.39.0',
      'sha256'  => {
        'amd64'   => '95c242a440e905bd36b8b5f803b7e546a5bd0ae1b6ffb4082e00bcd73d5b0dd4',
        'aarch64' => '6a67df30ab657bc84a1a3e7024592c9d78869bf86b8c23aafe09ecdb28cfdf01',
      },
    },
  }
}
