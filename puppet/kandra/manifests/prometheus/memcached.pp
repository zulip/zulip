# @summary Export memcached stats, with SASL auth
#
# We cannot use the stock
# https://github.com/prometheus/memcached_exporter because it does not
# support SASL auth, which we require.  Re-implement it in Python,
# using bmemcached.
class kandra::prometheus::memcached {
  include kandra::prometheus::base
  include zulip::supervisor

  # We embed the hash of the contents into the name of the process, so
  # that `supervisorctl reread` knows that it has updated.
  $full_exporter_hash = sha256(file('kandra/memcached_exporter'))
  $exporter_hash = $full_exporter_hash[0,8]

  $bin = '/usr/local/bin/memcached_exporter'
  file { $bin:
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/kandra/memcached_exporter',
  }

  kandra::firewall_allow { 'memcached_exporter': port => '11212' }
  file { "${zulip::common::supervisor_conf_dir}/memcached_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/memcached_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
