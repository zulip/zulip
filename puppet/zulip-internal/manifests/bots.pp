class zulip-internal::bots {
  include zulip-internal::base
  include zulip::supervisor

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    ensure => absent,
  }

}
