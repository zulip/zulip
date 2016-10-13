class zulip_internal::redis inherits zulip::redis {
  include zulip_internal::base

  File[ "/etc/redis/redis.conf"] {
    source => "puppet:///modules/zulip_internal/redis/redis.conf",
  }
}
