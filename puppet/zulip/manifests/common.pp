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
}
