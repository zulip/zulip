# Declare the apt class to manage /etc/apt/sources.list and /etc/sources.list.d
class { 'apt': }

# Install the puppetlabs apt source
# Release is automatically obtained from lsbdistcodename fact if available.
apt::source { 'puppetlabs':
  location   => 'http://apt.puppetlabs.com',
  repos      => 'main',
  key        => '4BD6EC30',
  key_server => 'pgp.mit.edu',
}

# test two sources with the same key
apt::source { 'debian_testing':
  location   => 'http://debian.mirror.iweb.ca/debian/',
  release    => 'testing',
  repos      => 'main contrib non-free',
  key        => '55BE302B',
  key_server => 'subkeys.pgp.net',
  pin        => '-10',
}
apt::source { 'debian_unstable':
  location   => 'http://debian.mirror.iweb.ca/debian/',
  release    => 'unstable',
  repos      => 'main contrib non-free',
  key        => '55BE302B',
  key_server => 'subkeys.pgp.net',
  pin        => '-10',
}
