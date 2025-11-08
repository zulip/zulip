# @summary Allows configuration of timesync tool.
class zulip::timesync {
  $timesync = zulipconf('machine', 'timesync', 'chrony')

  case $timesync {
    'chrony': {
      package { 'ntp': ensure => purged, before => Package['chrony'] }
      package { 'chrony': ensure => installed }
      service { 'chrony': require => Package['chrony'] }
    }
    'ntpd': {
      package { 'chrony': ensure => purged, before => Package['ntp'] }
      package { 'ntp': ensure => installed }
      service { 'ntp': require => Package['ntp'] }
    }
    'none': {
      package { ['ntp', 'chrony']: ensure => purged }
    }
    default: {
      fail('Unknown timesync tool: $timesync')
    }
  }
}
