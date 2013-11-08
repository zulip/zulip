class zulip::camo {
  $camo_packages = [# Needed for camo
                    "nodejs",
                    "camo",
                    ]
  package { $camo_packages: ensure => "installed" }

  # The configuration file is generated at install time
}


