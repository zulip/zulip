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

  if $facts['container_memory_limit_mb'] {
    $total_memory_mb = Integer($facts['container_memory_limit_mb'])
  } else {
    $total_memory_mb = Integer($facts['memory']['system']['total_bytes'] / 1024 / 1024)
  }

  $goarch = $facts['os']['architecture'] ? {
    'amd64'   => 'amd64',
    'aarch64' => 'arm64',
  }

  $versions = {
    # https://github.com/cactus/go-camo/releases
    'go-camo' => {
      'version'   => '2.7.1',
      'goversion' => '1252',
      'sha256'    => {
        'amd64'   => 'dd90f226d9305fcea4a91e90710615ed20b44339e3c4f4425356c80c3203ed8a',
        'aarch64' => 'a7f380eca870e0eb26774592271df9d8f2d325f8c45fec5cb989b5c3ef23135a',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.25.3',
      'sha256'  => {
        'amd64'   => '0335f314b6e7bfe08c3d0cfaa7c19db961b7b99fb20be62b0a826c992ad14e0f',
        'aarch64' => '1d42ebc84999b5e2069f5e31b67d6fc5d67308adad3e178d5a2ee2c9ff2001f5',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '3ec99c08f3a42840e6a5c9a47d0f85c6d591f52c',
      # Source code, so arch-invariant sha256
      'sha256'  => '32e18f5bb04001079a05996088ea33600bedd25b6abd0caf636049677a9e94a5',
    },

    # https://github.com/tus/tusd/releases
    # Keep in sync with tools/setup/install-tusd
    'tusd' => {
      'version' => '2.8.0',
      'sha256'  => {
        'amd64'   => 'e13c8adc9bed4c993a72f60140f688736058d2c3f4a18fb6e59ca26e829fb93b',
        'aarch64' => '089eb6d144df7cc5e10ac611a18f407308aedb3f9024a78fa01cb60ba99005a9',
      },
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '3.0.7',
      'sha256'  => {
        'amd64'   => '76d51ed915165d45314bc947300b9d1776adb2d875d857f580a730fd6f66900e',  # The ubuntu-22.04 version
        'aarch64' => 'fcf25aac732f66e77e121e9d287a08d8bf867c604b81cb6fcfff2d6c692d38c9',  # The ubuntu-22.04 version
      },
    },

    ### kandra packages

    # https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html
    'aws_signing_helper' => {
      'version' => '1.7.1',
      'sha256'  => {
        'amd64'   => '807f911124a7192bba23c6e8f37f6cb41e9defe4722fbeaf471e2c5951c6229c',
        'aarch64' => '5413ea1c86c1747254fc14450f44013ccec32901fb2b70f9105f5679dd6eaa5d',
      },
    },

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.56.1',
      'sha256'  => {
        'amd64'   => 'be0bcbf4740c95330cf2d735769f31640d69fd297a2b74ad0cd9ed383814cafa',
        'aarch64' => 'cc58bca49593cd6fcda4d934e1bf68f3bed9194156ba122cdb2e4cfd79a23878',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '12.2.0',
      'sha256'  => {
        'amd64'   => 'c4f53551ed4887c792caeb9d02fa0c1a36e3db9ee8bdda32b1ced810cb135a93',
        'aarch64' => 'ef84a75b6888e4674e3d2a21ae586cda61999ec202298e855c5de71fd242eb35',
      },
    },

    # https://github.com/fstab/grok_exporter/tags
    'grok_exporter' => {
      'version' => '1.0.0.RC5',
      'sha256'  => {
        'amd64' => 'b8771a6d7ca8447c222548d6cb8b2f8ee058b55bfd1801c2f6eb739534df5ded',
        # No aarch64 builds
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.9.1',
      'sha256'  => {
        'amd64'   => 'becb950ee80daa8ae7331d77966d94a611af79ad0d3307380907e0ec08f5b4e8',
        'aarch64' => '848f139986f63232ced83babe3cad1679efdbb26c694737edc1f4fbd27b96203',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.18.1',
      'sha256'  => {
        'amd64'   => '1630965540d49a4907ad181cef5696306d7a481f87f43978538997e85d357272',
        'aarch64' => '81c22dc2b6dcc58e9e2b5c0e557301dbf0ca0812ee3113d31984c1a37811d1cc',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => '8067b51a82bba267497d64b8708e141aa493450c',
      'sha256'  => '9b74d48019a46fafb88948c8209fa713ccd8d1c34a0d935593ddb301656f0871',
    },

    # https://github.com/ncabatoff/process-exporter/releases
    'process_exporter' => {
      'version' => '0.8.7',
      'sha256'  => {
        'amd64'   => '6d274cca5e94c6a25e55ec05762a472561859ce0a05b984aaedb67dd857ceee2',
        'aarch64' => '4a2502f290323e57eeeb070fc10e64047ad0cd838ae5a1b347868f75667b5ab0',
      }
    },

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '3.7.1',
      'sha256'  => {
        'amd64'   => 'a2e8a89c09b14b2277e6151e87fc8ed18858486cbf89372656d71fcd666b51da',
        'aarch64' => '7ede3f3f0541b9bfd2ccca9cef57af80554f131b8e7af8900896c6e49ed2d4ef',
      },
    },

    # https://github.com/prometheus/pushgateway/releases
    'pushgateway' => {
      'version' => '1.11.1',
      'sha256'  => {
        'amd64'   => '6ce6ffab84d0d71195036326640295c02165462abd12b8092b0fa93188f5ee37',
        'aarch64' => 'b6dc1c1c46d1137e5eda253f6291247e39330d3065a839857b947e59b4f3e64b',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.79.0',
      'sha256'  => {
        'amd64'   => 'cd584b0ec12dfb539c5df0c9cac9ca277f4383022576182e9ecb1df8c45642f0',
        'aarch64' => '278becb6e7343577846d76d7250a6c84bd18efb9fe893cf4f3d5ee9534b39496',
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
      'version' => '0.50.0',
      'sha256'  => {
        'amd64'   => '951ceb14f2382c1438696552745221c5584d6895f9aa2b0e12ff0e30271d4b0e',
        'aarch64' => 'ed73245a88638962093b9b5eb92ba3e17681a7b641e26eac674d07b137a605b8',
      },
    },
  }
}
