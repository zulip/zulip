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
      'version'   => '2.4.7',
      'goversion' => '1214',
      'sha256'    => {
        'amd64'   => '88742017c92ec71f386c343331b97ffe6fd14098d876cd902f86cfec2e47bb8a',
        'aarch64' => '85d5d0a13c50597a2f78c114fa5082417d2add385a90b175a076e49bf541e722',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.21.5',
      'sha256'  => {
        'amd64'   => 'e2bc0b3e4b64111ec117295c088bde5f00eeed1567999ff77bc859d7df70078e',
        'aarch64' => '841cced7ecda9b2014f139f5bab5ae31785f35399f236b8b3e75dff2a2978d96',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '8c0fa26edf63f35d5632ba7682d78ff07a306819',
      # Source code, so arch-invariant sha256
      'sha256'  => '496cddca7081671806ca7a8820db6f664ae8e491b3a9828d2dc9af12cda052e4',
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
      'version' => '2.23.0',
      'sha256'  => {
        'amd64'   => '23d3fdb2e797a1f49917b13cd040874f6189aff3f24d56d3fb81d74c1f368372',
        'aarch64' => '66d0b504d983ff2f7b5f60ebf5b3c933ba8a93c2a608f759863fd2b446b344fd',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '10.2.2',
      'sha256'  => {
        'amd64'   => '32dd2c8b94f1917190a79be6543dfb7e5dd6297bae21c24db624dc1180aba19f',
        'aarch64' => '96770f3f9bdfc662e0dbe57fbbb09206817935bca0e38755f942e0f65259e8c7',
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
      'version' => '2.48.0',
      'sha256'  => {
        'amd64'   => '5871ca9e01ae35bb7ab7a129a845a7a80f0e1453f00f776ac564dd41ff4d754e',
        'aarch64' => 'c6e85f7b4fd0785df48266c1ee53975f862996a99b7d96520dc730e65da7bcf6',
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
      'version' => '0.34.1',
      'sha256'  => {
        'amd64'   => '81a8bba16c58f2d31a80c5b5c7975ad74ff108c8ca835ad3df4ad0afe165d154',
        'aarch64' => '93291615d72f906a69660ef1a80db8fa5db55f7905cc0c85fb8443dbab5f2e3b',
      },
    },
  }
}
