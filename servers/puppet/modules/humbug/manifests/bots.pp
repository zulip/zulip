class humbug::bots {
  class { 'humbug::base': }
  class { 'humbug::supervisor': }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    require => Package['supervisor'],
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => 640,
    source  => "puppet:///modules/humbug/supervisord/conf.d/feedback-bot.conf",
    notify  => Service['supervisor'],
  }
}
