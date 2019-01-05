class zulip::common {
  # Common parameters
  case $::osfamily {
    'debian': {
      $nagios_plugins = 'nagios-plugins-basic'
      $nagios_plugins_dir = '/usr/lib/nagios/plugins'
      $nginx = 'nginx-full'
      $supervisor_conf_dir = '/etc/supervisor/conf.d'
      $supervisor_service = 'supervisor'
    }
    'redhat': {
      $nagios_plugins = 'nagios-plugins'
      $nagios_plugins_dir = '/usr/lib64/nagios/plugins'
      $nginx = 'nginx'
      $supervisor_conf_dir = '/etc/supervisord.d/conf.d'
      $supervisor_service = 'supervisord'
    }
    default: {
      fail('osfamily not supported')
    }
  }
}
