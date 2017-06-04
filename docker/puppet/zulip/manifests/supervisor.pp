class zulip::supervisor {
  $supervisor_packages = [
    # Needed to run supervisor
    "supervisor",
  ]
  package { $supervisor_packages: ensure => "installed" }

  file { "/etc/supervisor/supervisord.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisor/supervisord.conf",
  }

  file { '/etc/supervisor/conf.d':
    require => Package[supervisor],
    ensure => 'directory',
    owner => 'root',
    group => 'root',
  }
}
