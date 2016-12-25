# Class: zulip::thumbor
#
#
class zulip::thumbor {
  $thumbor_packages = [
    "libssl-dev",
    "libcurl4-openssl-dev",
    "libjpeg-dev",
    "libpng-dev",
    "libtiff-dev",
    "libjasper-dev",
    "libgtk2.0-dev",
    "libwebp-dev",
    "webp",
    "gifsicle"
  ]

  package { $thumbor_packages: ensure => "installed" }

  file { "/etc/supervisor/conf.d/thumbor.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisor/conf.d/thumbor.conf",
    notify => Service["supervisor"],
  }
}
