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

  $goarch = $::architecture ? {
    'amd64'   => 'amd64',
    'aarch64' => 'arm64',
  }

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
      'version' => '1.17.3',
      'sha256' => {
        'amd64'   => '550f9845451c0c94be679faf116291e7807a8d78b43149f9506c1b15eb89008c',
        'aarch64' => '06f505c8d27203f78706ad04e47050b49092f1b06dc9ac4fbee4f0e4d015c8d4',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => 'dc403015f563eadc556a61870c6ad327688abe88',
      # Source code, so arch-invariant sha256
      'sha256' => 'ad4b181d14adcd9425045152b903a343dbbcfcad3c1e7625d2c65d1d50e1959d',
    },

    # https://github.com/wal-g/wal-g/releases
    'wal-g' => {
      'version' => '1.1.1-rc',
      'sha256' => {
        'amd64' => 'eed4de63c2657add6e0fe70f8c0fbe62a4a54405b9bfc801b1912b6c4f2c7107',
        # No aarch64 builds
      },
    },
  }
}
