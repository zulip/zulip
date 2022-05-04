class zulip_ops::profile::nagios {
  include zulip_ops::profile::base
  include zulip_ops::apache

  $nagios_packages = [# Packages needed for Nagios
                      'nagios4',
                      # For sending outgoing email
                      'msmtp',
                      ]
  package { $nagios_packages: ensure => installed }
  $nagios_alert_email = zulipconf('nagios', 'alert_email', undef)
  $nagios_test_email = zulipconf('nagios', 'test_email', undef)
  $nagios_pager_email = zulipconf('nagios', 'pager_email', undef)

  $nagios_mail_domain = zulipconf('nagios', 'mail_domain', undef)
  $nagios_mail_host = zulipconf('nagios', 'mail_host', undef)
  $nagios_mail_password = zulipsecret('secrets', 'nagios_mail_password', '')
  if zulipconf('nagios', 'camo_check_url', undef) =~ /^https:\/\/([^\/]*)(\/.*)$/ {
    $nagios_camo_check_host = $1
    $nagios_camo_check_path = $2
  }

  $default_host_domain = zulipconf('nagios', 'default_host_domain', undef)
  $hosts_zmirror = split(zulipconf('nagios', 'hosts_zmirror', undef), ',')
  $hosts_zmirrorp = split(zulipconf('nagios', 'hosts_zmirrorp', undef), ',')
  $hosts_app_prod = split(zulipconf('nagios', 'hosts_app_prod', undef), ',')
  $hosts_app_staging = split(zulipconf('nagios', 'hosts_app_staging', undef), ',')
  $hosts_postgresql_primary = split(zulipconf('nagios', 'hosts_postgresql_primary', undef), ',')
  $hosts_postgresql_replica = split(zulipconf('nagios', 'hosts_postgresql_replica', undef), ',')
  $hosts_redis = split(zulipconf('nagios', 'hosts_redis', undef), ',')
  $hosts_stats = split(zulipconf('nagios', 'hosts_stats', undef), ',')
  $hosts_fullstack = split(zulipconf('nagios', 'hosts_fullstack', undef), ',')
  $hosts_smokescreen = split(zulipconf('nagios', 'hosts_smokescreen', undef), ',')

  file { '/etc/nagios4/':
    recurse => true,
    purge   => false,
    require => Package[nagios4],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/nagios4/',
    notify  => Service['nagios4'],
  }

  file { '/etc/apache2/sites-available/nagios.conf':
    purge   => false,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    content => template('zulip_ops/nagios_apache_site.conf.template.erb'),
  }
  apache2site { 'nagios':
    ensure  => present,
    require => [
      File['/etc/apache2/sites-available/nagios.conf'],
      Apache2mod['headers'], Apache2mod['ssl'],
    ],
    notify  => Service['apache2'],
  }
  zulip_ops::teleport::application{ 'nagios':
    description => 'Monitoring: nagios and munin',
    port        => '3000',
  }

  file { '/etc/nagios4/conf.d/contacts.cfg':
    require => Package[nagios4],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/nagios4/contacts.cfg.template.erb'),
    notify  => Service['nagios4'],
  }
  file { '/etc/nagios4/conf.d/hosts.cfg':
    require => Package[nagios4],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/nagios4/hosts.cfg.template.erb'),
    notify  => Service['nagios4'],
  }
  file { '/etc/nagios4/conf.d/localhost.cfg':
    require => Package[nagios4],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/nagios4/localhost.cfg.template.erb'),
    notify  => Service['nagios4'],
  }

  file { '/etc/nagios4/cgi.cfg':
    require => Package[nagios4],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/nagios4/cgi.cfg.template.erb'),
    notify  => Service['nagios4'],
  }

  service { 'nagios4':
    ensure => running,
  }

  file { [
    '/etc/nagios4/conf.d/extinfo_nagios2.cfg',
    '/etc/nagios4/conf.d/services_nagios2.cfg',
    '/etc/nagios4/conf.d/contacts_nagios2.cfg',
    '/etc/nagios4/conf.d/hostgroups_nagios2.cfg',
    '/etc/nagios4/conf.d/localhost_nagios2.cfg',
  ]:
    ensure     => absent,
  }

  file { '/etc/nagios4/conf.d/zulip_nagios.cfg':
    ensure => file,
    mode   => '0644',
    owner  => 'root',
    group  => 'root',
    source => '/usr/local/share/zulip/integrations/nagios/zulip_nagios.cfg',
    notify => Service['nagios4'],
  }

  $hosts = zulipconf_nagios_hosts()
  file { '/etc/nagios4/conf.d/zulip_autossh.cfg':
    ensure  => file,
    mode    => '0644',
    owner   => 'root',
    group   => 'root',
    content => template('zulip_ops/nagios_autossh.template.erb'),
    notify  => Service['nagios4'],
  }

  file { '/var/lib/nagios/msmtprc':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => template('zulip_ops/msmtprc_nagios.template.erb'),
    require => File['/var/lib/nagios'],
  }

  # Disable apparmor for msmtp so it can read the above config file
  file { '/etc/apparmor.d/disable/usr.bin.msmtp':
    ensure => link,
    target => '/etc/apparmor.d/usr.bin.msmtp',
    notify => Exec['reload apparmor'],
  }
  exec {'reload apparmor':
    command     => '/sbin/apparmor_parser -R /etc/apparmor.d/usr.bin.msmtp',
    refreshonly => true,
  }

  exec { 'fix_nagios_permissions':
    command => 'dpkg-statoverride --update --add nagios www-data 2710 /var/lib/nagios4/rw',
    unless  => 'bash -c "ls -ld /var/lib/nagios4/rw | grep ^drwx--s--- -q"',
    notify  => Service['nagios4'],
  }
  exec { 'fix_nagios_permissions2':
    command => 'dpkg-statoverride --update --add nagios nagios 751 /var/lib/nagios4',
    unless  => 'bash -c "ls -ld /var/lib/nagios4 | grep ^drwxr-x--x -q"',
    notify  => Service['nagios4'],
  }

  # TODO: Install our API
}
