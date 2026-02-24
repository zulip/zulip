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
      'version'   => '2.7.3',
      'goversion' => '1260',
      'sha256'    => {
        'amd64'   => 'd1071300b6692d194a439cb4e380ff95e1f4d894e2318bf47aaec077722370b7',
        'aarch64' => '22afef25d43cb0cb44dac100ec5602846bd66de0d9d3a3c6fc2c98eae82e6639',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.26.0',
      'sha256'  => {
        'amd64'   => 'aac1b08a0fb0c4e0a7c1555beb7b59180b05dfc5a3d62e40e9de90cd42f88235',
        'aarch64' => 'bd03b743eb6eb4193ea3c3fd3956546bf0e3ca5b7076c8226334afe6b75704cd',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '464b1115f802cbd91ffee555a41e71546646d396',
      # Source code, so arch-invariant sha256
      'sha256'  => '800d455bbdd23df0587b72e05e9bb51ce80d0f5816bd1b7070c2c26f4340cfca',
    },

    # https://github.com/tus/tusd/releases
    # Keep in sync with tools/setup/install-tusd
    'tusd' => {
      'version' => '2.9.1',
      'sha256'  => {
        'amd64'   => '140066be543e40493abd1fda1d1e33ab7fa0e8b9a61d247130f6777e64bf28f6',
        'aarch64' => 'c9c46eba6e46b8062f863af6a5423f6f72b5157939d967087cd9b6d7c6bd19cf',
      },
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '3.0.8',
      'sha256'  => {
        'amd64'   => 'f30544c5ce93cf83b87578e3c4a2e9c0e0ffc3d160ef89ecddaf75f397d98deb',  # The ubuntu-22.04 version
        'aarch64' => '794d1a81f0c27825a1603bd39c0f2cf5dd8bed7cc36b598ca05d8d963c3d5fcf',  # The ubuntu-22.04 version
      },
    },

    ### kandra packages

    # https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html
    'aws_signing_helper' => {
      'version' => '1.7.3',
      'sha256'  => {
        'amd64'   => 'ef609ae021e86a2778b63dc80f4280033fcb1450bddb8b234b4ccd30f917ed21',
        'aarch64' => '7aaf8b3a4ceac464931dec27bcfd58e4facc93fb48402381e3f96bb45de5a356',
      },
    },

    # https://release-registry.services.sentry.io/apps/sentry-cli/latest
    'sentry-cli' => {
      'version' => '2.58.4',
      'sha256'  => {
        'amd64'   => 'a4932b4315b192b3d037678a16eb2a5a8731609f671fc4008e643b85c3c74cb6',
        'aarch64' => '672cb986b0c5d84ef724f39b3aa189be802bceb8bc7dc8c5776a0ca90fcf41bd',
      },
    },

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '12.3.3',
      'sha256'  => {
        'amd64'   => 'd69b850d02903bcfe27289661c5b0b1b9a67d0bf0c42d344d55d0e63e62a7bda',
        'aarch64' => 'a2a50f6a63c89c59914b604482500de2648d12ee266d8eac8886815710482614',
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
      'version' => '1.10.2',
      'sha256'  => {
        'amd64'   => 'c46e5b6f53948477ff3a19d97c58307394a29fe64a01905646f026ddc32cb65b',
        'aarch64' => 'de69ec8341c8068b7c8e4cfe3eb85065d24d984a3b33007f575d307d13eb89a6',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/tags
    'postgres_exporter' => {
      'version' => '0.19.0',
      'sha256'  => {
        'amd64'   => '11033f9016d0c5a5b91742d17aa37490b170f055ec1bb0d7d69509d223952ed0',
        'aarch64' => '8a2f55b1a00694758ea4bfd96a8bb814c1b279cf9d233a24fecd28a9e87c6280',
      },
    },

    # https://github.com/prometheus-community/postgres_exporter/pull/843
    'postgres_exporter-src' => {
      'version' => '86a2b77aa522f57a136d04ffa33f0e46713d1925',
      'sha256'  => '03b3a4e794b6c01e911c3f7f4d77a2889d6946e2245f8d12d14844c29554a884',
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
      'version' => '3.9.1',
      'sha256'  => {
        'amd64'   => '86a6999dd6aacbd994acde93c77cfa314d4be1c8e7b7c58f444355c77b32c584',
        'aarch64' => '4e7f291e527d8aca912a995c183128388c9e048065aff84f74f5a55c9bef3793',
      },
    },

    # https://github.com/prometheus/pushgateway/releases
    'pushgateway' => {
      'version' => '1.11.2',
      'sha256'  => {
        'amd64'   => '2ec72315e150dda071fdeef09360780a386a67e5207ebaa53bb18f2f1a3b89cf',
        'aarch64' => 'b3fb835dbb0a29b1d6f9cd7ae3568a5615e59b96f8787965248cea67163d4db1',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.81.0',
      'sha256'  => {
        'amd64'   => 'd2f4740fa81e1a274ca99677783f3fe1544f6022fed997d4cd632d01a8eff1bb',
        'aarch64' => '038d0d2d8f044075cc97acd323c16a8c3628f08ef7d186601fedaa38b71aad8f',
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
      'version' => '0.53.0',
      'sha256'  => {
        'amd64'   => '5460f93310eb59cc9e7ee7717a179f1bf2ff8fbc046b7e3eb625159a5e8714bb',
        'aarch64' => '2722dec4f5c358793caeb86b4f4febd047b37a2d688af181e8264a764ecd28e5',
      },
    },
  }
}
