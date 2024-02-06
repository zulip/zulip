# @summary Munin monitoring of a Django frontend and RabbitMQ server.
#
class kandra::app_frontend_monitoring {
  include kandra::prometheus::rabbitmq
  include kandra::prometheus::uwsgi
  include kandra::prometheus::process
  kandra::firewall_allow { 'grok_exporter': port => '9144' }
  include kandra::munin_node
  $munin_plugins = [
    'rabbitmq_connections',
    'rabbitmq_consumers',
    'rabbitmq_messages',
    'rabbitmq_messages_unacknowledged',
    'rabbitmq_messages_uncommitted',
    'rabbitmq_queue_memory',
    'zulip_send_receive_timing',
  ]
  kandra::munin_plugin { $munin_plugins: }

  file { '/etc/cron.d/rabbitmq-monitoring':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/rabbitmq-monitoring',
  }
}
