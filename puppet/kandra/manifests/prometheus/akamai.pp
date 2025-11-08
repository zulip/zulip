# @summary Prometheus monitoring of Akamai access logs
#
class kandra::prometheus::akamai {
  include kandra::prometheus::base
  include kandra::vector
  include zulip::supervisor

  $pipelines = {
    'static' => zulipsecret('secrets', 'akamai_static_sqs_url', ''),
    'realm'  => zulipsecret('secrets', 'akamai_realm_sqs_url', ''),
  }

  concat::fragment { 'vector_akamai':
    target  => $kandra::vector::conf,
    order   => '50',
    content => template('kandra/vector_akamai.toml.template.erb'),
  }
  concat::fragment { 'vector_akamai_export':
    target  => $kandra::vector::conf,
    content => ',"akamai_logs2metrics*"',
    order   => '90',
  }
}
