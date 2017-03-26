# This adds the necessary components to get backports for ubuntu and debian
#
# == Parameters
#
# [*release*]
#   The ubuntu/debian release name. Defaults to $lsbdistcodename. Setting this
#   manually can cause undefined behavior. (Read: universe exploding)
#
# == Examples
#
#   include apt::backports
#
#   class { 'apt::backports':
#     release => 'natty',
#   }
#
# == Authors
#
# Ben Hughes, I think. At least blame him if this goes wrong.
# I just added puppet doc.
#
# == Copyright
#
# Copyright 2011 Puppet Labs Inc, unless otherwise noted.
class apt::backports(
  $release  = $::lsbdistcodename,
  $location = $apt::params::backports_location
) inherits apt::params {

  $release_real = downcase($release)
  $key = $::lsbdistid ? {
    'debian' => '55BE302B',
    'ubuntu' => '437D05B5',
  }
  $repos = $::lsbdistid ? {
    'debian' => 'main contrib non-free',
    'ubuntu' => 'main universe multiverse restricted',
  }

  apt::source { 'backports':
    location   => $location,
    release    => "${release_real}-backports",
    repos      => $repos,
    key        => $key,
    key_server => 'pgp.mit.edu',
    pin        => '200',
  }
}
