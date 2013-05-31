class humbug::bots {
  class { 'humbug::base': }

  $bots_packages = [ "supervisor" ]
  package { $bots_packages: ensure => "installed" }

  file { '/var/log/humbug':
    ensure => 'directory',
    owner  => 'humbug',
    group  => 'humbug',
    mode   => 640,
  }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    require => Package['supervisor'],
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => 640,
    source  => "puppet:///modules/humbug/supervisord/conf.d/feedback-bot.conf",
  }
}
