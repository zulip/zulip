class zulip::sasl_modules {
  $sasl_module_packages = $facts['os']['family'] ? {
    'Debian' => [ 'libsasl2-modules' ],
    'RedHat' => [ 'cyrus-sasl-plain' ],
  }
  package { $sasl_module_packages: ensure => installed }
}
