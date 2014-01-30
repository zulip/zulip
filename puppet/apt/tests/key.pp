# Declare Apt key for apt.puppetlabs.com source
apt::key { 'puppetlabs':
  key         => '4BD6EC30',
  key_server  => 'pgp.mit.edu',
  key_options => 'http-proxy="http://proxyuser:proxypass@example.org:3128"',
}
