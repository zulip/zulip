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
      'version'   => '2.6.3',
      'goversion' => '1242',
      'sha256'    => {
        'amd64'   => '8ac2122a822366ba4c628fcd99d53e73ac0292456a4cf53548a711ca5500b6d3',
        'aarch64' => 'a391d1686c604f7f930ac8d31fb3265a6f1841aab8b7ee426391f1bbf1617b15',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.24.4',
      'sha256'  => {
        'amd64'   => '77e5da33bb72aeaef1ba4418b6fe511bc4d041873cbf82e5aa6318740df98717',
        'aarch64' => 'd5501ee5aca0f258d5fe9bfaed401958445014495dc115f202d43d5210b45241',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '1b618edf4d3dda409ab7a00cdf3f202e143b5289',
      # Source code, so arch-invariant sha256
      'sha256'  => '19ffe07eaab321b3ce33b64d893a09ffc9cb520c8672458b761d0a76147079e3',
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
      'version' => '1.7.0',
      'sha256'  => {
        'amd64'   => 'e932f029b73f97523c1dea2e78e9543d9e2753c387c4c46e77be8c1d9424db0f',
        'aarch64' => '800fc208b74cdb64b8c7270c41aa0c9d2f9bf5bba498539513acb30f8eb8f164',
      },
    },

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.46.0',
      'sha256'  => {
        'amd64'   => 'a55b96a0d5391c5206c2bc028e52dd9797dc3646556291cca09d00a19707f85e',
        'aarch64' => '00b292f4edc9c13b079123b574abe73c012b7357426d34bbbf0bd0a5ab59a491',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '12.0.2',
      'sha256'  => {
        'amd64'   => 'c1755b4da918edfd298d5c8d5f1ffce35982ad10e1640ec356570cfb8c34b3e8',
        'aarch64' => 'bc0b186458cc91e2f96a06ecff2b3b4033b1a6ffd2449817e2a430a0b4ae4f12',
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
      'version' => '0.17.1',
      'sha256'  => {
        'amd64'   => '6da7d2edafd69ecceb08addec876786fa609849f6d5f903987c0d61c3fc89506',
        'aarch64' => '405af4e838a3d094d575e5aaeac43bd0a1818aaf2c840a3c8fc2c6fcc77218dc',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => 'a90028d313e914d0736c94bb896c06818afcefb1',
      'sha256'  => 'b52909bda1fc60bcdde1dd800e4d088a7a5027ecafa152e034d30e82329dba41',
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
      'version' => '3.4.1',
      'sha256'  => {
        'amd64'   => '09203151c132f36b004615de1a3dea22117ad17e6d7a59962e34f3abf328f312',
        'aarch64' => '2a85be1dff46238c0d799674e856c8629c8526168dd26c3de2cecfbfc6f9a0a2',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.74.0',
      'sha256'  => {
        'amd64'   => '481830d1a238cadfb84dacef9381012c7b2aa1d400baa9bc551995b8839f55a3',
        'aarch64' => 'a864fed00d83c4f43257738abd0cd09343b075591eae2ee43a573e0c9693c36c',
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
      'version' => '0.47.0',
      'sha256'  => {
        'amd64'   => '478c1c85a0279e9f05a4253b518c8e93b6e2154e36e8cb3d8d77c2e496316682',
        'aarch64' => '614ff0481a901ece8634e734c94c318bf63fca34d00d0605e456dbfa3b5f80b8',
      },
    },
  }
}
