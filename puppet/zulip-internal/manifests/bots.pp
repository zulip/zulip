class zulip-internal::bots {
  class { 'zulip-internal::base': }
  class { 'zulip::supervisor': }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    ensure => absent,
  }

}
