class zulip::camo {
  $camo_packages = [# Needed for camo
                    "nodejs",
                    "camo",
                    ]
  package { $camo_packages: ensure => "installed" }

  $camo_key = zulipsecret("secrets", "camo_key", '')

  file { "/etc/default/camo":
    require => Package[camo],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    content => template("zulip/camo_defaults.template.erb"),
  }
}


