class zulip::common {
  # Common parameters
  case $::osfamily {
    'debian': {
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
    'redhat': {
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

  $total_memory_mb = Integer($::memorysize_mb)

  $versions = {
    # https://github.com/cactus/go-camo/releases
    'go-camo' => {
      'version' => '2.3.0',
      'sha256' => {
        'amd64'   => '965506e6edb9d974c810519d71e847afb7ca69d1d01ae7d8be6d7a91de669c0c',
        'aarch64' => '40463f6790eb0d2da69ad6a902fcc4c6b0c0ac24106a6c28fbfce9dfa4cb15cd',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.17.5',
      'sha256' => {
        'amd64'   => 'bd78114b0d441b029c8fe0341f4910370925a4d270a6a590668840675b0c653e',
        'aarch64' => '6f95ce3da40d9ce1355e48f31f4eb6508382415ca4d7413b1e7a3314e6430e7e',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '96dc8b043d3f22dcb65a9c2ccf22e3794e2da3a1',
      # Source code, so arch-invariant sha256
      'sha256' => 'c2b8080999c3ba9e2b509f8d4cf300922557e7c070fb16ac7d1ea220416f8660',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '1.1.1-rc',
      'sha256' => {
        'amd64' => 'eed4de63c2657add6e0fe70f8c0fbe62a4a54405b9bfc801b1912b6c4f2c7107',
        # No aarch64 builds
      },
    },


    ### zulip_ops packages

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '8.3.3',
      'sha256' => {
        'amd64'   => '89428c520e004bcb9faf7618dd4c81ff62496064cbf2ead3e1b9dbcf476c6f18',
        'aarch64' => '6252917d7e63eb47e0955125b3b2c1c5d3e4d2e3bb84c269a8d86bd073a1dce7',
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

    # https://prometheus.io/download/#prometheus
    'prometheus' => {
      'version' => '2.32.1',
      'sha256' => {
        'amd64'   => 'f08e96d73330a9ee7e6922a9f5b72ea188988a083bbfa9932359339fcf504a74',
        'aarch64' => '2d185a8ed46161babeaaac8ce00ef1efdeccf3ef4ed234cd181eac6cad1ae4b2',
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
