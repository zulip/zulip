class zulip::common {
  # Common parameters
  case $::osfamily {
    'debian': {
      $nagios_plugins = 'nagios-plugins-basic'
      $nagios_plugins_dir = '/usr/lib/nagios/plugins'
      $nginx = 'nginx-full'
    }
    'redhat': {
      $nagios_plugins = 'nagios-plugins'
      $nagios_plugins_dir = '/usr/lib64/nagios/plugins'
      $nginx = 'nginx'
    }
    default: {
      fail('osfamily not supported')
    }
  }
}
