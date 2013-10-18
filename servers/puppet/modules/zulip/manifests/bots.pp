class zulip::bots {
  class { 'zulip::base': }
  class { 'zulip::supervisor': }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    ensure => absent,
  }

}
