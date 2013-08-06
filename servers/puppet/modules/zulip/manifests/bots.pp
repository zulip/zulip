class zulip::bots {
  class { 'zulip::base': }
  class { 'zulip::supervisor': }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    require => Package['supervisor'],
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => 640,
    source  => "puppet:///modules/zulip/supervisord/conf.d/feedback-bot.conf",
    notify  => Service['supervisor'],
  }
}
