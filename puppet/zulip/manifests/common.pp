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

  # Versions and sha256s for third-party binaries and source archives.
  # Consumed via $zulip::common::versions[<name>]['version'] /
  # ['sha256'][<arch>].  Updated by tools/update-dependency-versions,
  # which reads the same file for updater metadata (_updater subtree).
  $versions = parsejson(file('zulip/dependencies.json'))
}
