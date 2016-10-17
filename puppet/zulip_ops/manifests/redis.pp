class zulip_ops::redis inherits zulip::redis {
  include zulip_ops::base

  File[ "/etc/redis/redis.conf"] {
    source => "puppet:///modules/zulip_ops/redis/redis.conf",
  }
}
