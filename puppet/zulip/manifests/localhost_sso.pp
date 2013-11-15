class zulip::localhost_sso {
  file { "/etc/nginx/zulip-include/app.d/external-sso.conf":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/zulip-include-app.d/external-sso.conf",
  }
}
