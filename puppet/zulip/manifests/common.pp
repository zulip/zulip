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
      'version'   => '2.4.1',
      'goversion' => '1191',
      'sha256'    => {
        'amd64'   => '8f4c715c44e18efc1fe5ce3e3e25f9b02442e46cf4e11df7d8d77d5305121f4b',
        'aarch64' => 'e3750345f51a5df198c287749a99d4222fbe55fb0be6872643dfe466db1768da',
      },
    },

    # https://go.dev/dl/
    'golang' => {
      'version' => '1.19.3',
      'sha256'  => {
        'amd64'   => '74b9640724fd4e6bb0ed2a1bc44ae813a03f1e72a4c76253e2d5c015494430ba',
        'aarch64' => '99de2fe112a52ab748fb175edea64b313a0c8d51d6157dba683a6be163fd5eab',
      },
    },

    # https://github.com/stripe/smokescreen/tags
    'smokescreen-src' => {
      'version' => '5b7c3b74c3243e167cb650a91406c11e80532319',
      # Source code, so arch-invariant sha256
      'sha256'  => 'e93d19b28fca0757ead502976a6ea71406b8b2a6fce536386c861fd97e257297',
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

    # https://grafana.com/grafana/download?edition=oss
    'grafana' => {
      'version' => '9.2.4',
      'sha256'  => {
        'amd64'   => '94d9cbea08120a9c51c29dfe66c8c85ef817af03b3ceb50bbb1b2bb2ee3bc07b',
        'aarch64' => 'd7d7c5c8625c4fe92c100504d9168b68a12c87edf091da66027de9aa99571afb',
      },
    },

    # https://prometheus.io/download/#node_exporter
    'node_exporter' => {
      'version' => '1.4.0',
      'sha256'  => {
        'amd64'   => 'e77ff1b0a824a4e13f82a35d98595fe526849c09e3480d0789a56b72242d2abc',
        'aarch64' => '0b20aa75385a42857a67ee5f6c7f67b229039a22a49c5c61c33f071356415b59',
      },
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
      'version' => '2.40.0',
      'sha256'  => {
        'amd64'   => '005d3337420e4390ca80bb97960cd9ac31f38ae6065cb1e8f8298c35d1b257aa',
        'aarch64' => 'c38d374624d329b64bb94bf9b25d7720d928a3117e4758546865d93059f14e53',
      },
    },

    # https://github.com/oliver006/redis_exporter/releases
    'redis_exporter' => {
      'version' => '1.45.0',
      'sha256'  => {
        'amd64'   => '0890f4a75c41a953b608a3c025ef735296a473e0119ed31864c8510efe7a8393',
        'aarch64' => 'f18144cdd7876979c7278507ccb68b87801b0df977825d76f0293173653d3dd7',
      },
    },

    # https://github.com/timonwong/uwsgi_exporter/releases
    'uwsgi_exporter' => {
      'version' => '1.1.0',
      'sha256'  => {
        'amd64'   => '28c7eb81515a08246824019fc42aa16c9bb3effafbcc150ab083e29295ba1fe3',
        'aarch64' => 'c8143ebd56f5d0e9eb84e3d091613cc656ea96bd176e7ff9ace9cd58e8358dc3',
      },
    },
  }
}
