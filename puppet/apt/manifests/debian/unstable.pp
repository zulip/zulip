# unstable.pp

class apt::debian::unstable {
  include apt

  # deb http://debian.mirror.iweb.ca/debian/ unstable main contrib non-free
  # deb-src http://debian.mirror.iweb.ca/debian/ unstable main contrib non-free
  # Key: 55BE302B  Server: subkeys.pgp.net
  # debian-keyring
  # debian-archive-keyring

  apt::source { 'debian_unstable':
    location          => 'http://debian.mirror.iweb.ca/debian/',
    release           => 'unstable',
    repos             => 'main contrib non-free',
    required_packages => 'debian-keyring debian-archive-keyring',
    key               => '55BE302B',
    key_server        => 'subkeys.pgp.net',
    pin               => '-10',
  }
}
