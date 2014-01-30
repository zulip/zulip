# release.pp

class apt::release (
  $release_id
) {

  include apt::params

  $root = $apt::params::root

  file { "${root}/apt.conf.d/01release":
    owner   => root,
    group   => root,
    mode    => '0644',
    content => "APT::Default-Release \"${release_id}\";"
  }
}
