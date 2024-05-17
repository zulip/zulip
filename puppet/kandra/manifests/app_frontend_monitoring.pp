# @summary Prometheus monitoring of a Django frontend and RabbitMQ server.
#
class kandra::app_frontend_monitoring {
  include kandra::prometheus::memcached
  include kandra::prometheus::rabbitmq
  include kandra::prometheus::uwsgi
  include kandra::prometheus::process
  kandra::firewall_allow { 'grok_exporter': port => '9144' }
  file { '/etc/cron.d/rabbitmq-monitoring':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/kandra/cron.d/rabbitmq-monitoring',
  }
}
