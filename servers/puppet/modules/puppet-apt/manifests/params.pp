class apt::params {

  $manage_preferences = $apt_manage_preferences ? {
    ''      => true,
    default => $apt_manage_preferences,
  }

  $manage_sourceslist = $apt_manage_sourceslist ? {
    ''      => true,
    default => $apt_manage_sourceslist,
  }

  $ignore_sourceslist = $apt_ignore_sourceslist ? {
    ''      => '.placeholder',
    default => $apt_ignore_sourceslist,
  }

  $keyring_package = $::lsbdistid ? {
    Debian => ['debian-keyring', 'debian-archive-keyring'],
    Ubuntu => 'ubuntu-keyring',
  }

}
