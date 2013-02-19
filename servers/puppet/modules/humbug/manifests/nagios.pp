class humbug::nagios {
  class { 'humbug::base': }
  class { 'humbug::apache': }

  $nagios_packages = [ "nagios3", "munin", "autossh" ]
  package { $nagios_packages: ensure => "installed" }

  apache2site { 'nagios':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
  #TODO: Need to install our Nagios config
  #
  # Also need to run this sequence to enable commands to set the
  # permissions for using the Nagios commands feature
  #
  # /etc/init.d/nagios3 stop
  # dpkg-statoverride --update --add nagios www-data 2710 /var/lib/nagios3/rw
  # dpkg-statoverride --update --add nagios nagios 751 /var/lib/nagios3
  # /etc/init.d/nagios3 start
  #
  #

  # TODO: Install our API
  # TODO: Install humbug_nagios.cfg from our API.
  # TODO: Install pagerduty_nagios.pl from http://www.pagerduty.com/docs/nagios-integration-guide/
  # TODO: Install the pagerduty_nagios cron job as well (pagerduty config is already in puppet)
}
