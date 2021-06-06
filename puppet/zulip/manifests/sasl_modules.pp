class zulip::sasl_modules {
  $sasl_module_packages = $::osfamily ? {
    'debian' => [ 'libsasl2-modules' ],
    'redhat' => [ 'cyrus-sasl-plain' ],
  }
  package { $sasl_module_packages: ensure => 'installed' }
}
