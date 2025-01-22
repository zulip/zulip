class zulip::snakeoil {
  zulip::safepackage { 'ssl-cert': ensure => installed }

  # We use the snakeoil certificate for PostgreSQL; some VMs install
  # the `ssl-cert` package but (reasonably) don't build the snakeoil
  # certs into the image; build them as needed.
  exec { 'generate-default-snakeoil':
    require => Package['ssl-cert'],
    creates => '/etc/ssl/certs/ssl-cert-snakeoil.pem',
    command => '/usr/sbin/make-ssl-cert generate-default-snakeoil',
  }
}
