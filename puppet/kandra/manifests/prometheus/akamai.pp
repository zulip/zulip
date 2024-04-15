# @summary Prometheus monitoring of Akamai access logs
#
class kandra::prometheus::akamai {
  include kandra::prometheus::base
  include kandra::vector
  include zulip::supervisor

  $bin = $kandra::vector::bin
  $conf = '/etc/vector.toml'
  $pipelines = {
    'static' => zulipsecret('secrets', 'akamai_static_sqs_url', ''),
    'realm'  => zulipsecret('secrets', 'akamai_realm_sqs_url', ''),
  }

  file { $conf:
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/vector.toml.template.erb'),
  }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_akamai_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File['/etc/vector.toml'],
      File[$bin],
    ],
    before  => Exec['Cleanup vector'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_akamai_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
