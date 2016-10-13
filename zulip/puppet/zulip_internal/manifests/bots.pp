class zulip_internal::bots {
  include zulip_internal::base
  include zulip::supervisor

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    ensure => absent,
  }

}
