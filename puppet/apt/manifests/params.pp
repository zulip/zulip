class apt::params {
  $root           = '/etc/apt'
  $provider       = '/usr/bin/apt-get'
  $sources_list_d = "${root}/sources.list.d"
  $apt_conf_d     = "${root}/apt.conf.d"
  $preferences_d  = "${root}/preferences.d"

  case $::lsbdistid {
    'debian': {
      case $::lsbdistcodename {
        'squeeze': {
          $backports_location = 'http://backports.debian.org/debian-backports'
        }
        'wheezy': {
          $backports_location = 'http://ftp.debian.org/debian/'
        }
        default: {
          $backports_location = 'http://http.debian.net/debian/'
        }
      }
    }
    'ubuntu': {
      case $::lsbdistcodename {
        'hardy','lucid','maverick','natty','oneiric','precise': {
          $backports_location = 'http://us.archive.ubuntu.com/ubuntu'
        }
        default: {
          $backports_location = 'http://old-releases.ubuntu.com/ubuntu'
        }
      }
    }
  }
}
