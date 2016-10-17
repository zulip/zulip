class zulip_ops::bots {
  include zulip_ops::base
  include zulip::supervisor

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    ensure => absent,
  }

}
