class zulip::localhost_camo {
  include zulip::camo

  # Install nginx configuration to run camo locally
  file { "/etc/nginx/zulip-include/app.d/camo.conf":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/zulip-include-app.d/camo.conf",
  }
}
