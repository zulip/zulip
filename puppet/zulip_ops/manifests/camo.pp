class zulip_ops::camo {
  class { 'zulip::camo':
    listen_address => '0.0.0.0',
  }
}
