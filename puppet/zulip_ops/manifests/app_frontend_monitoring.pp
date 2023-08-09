# @summary Munin monitoring of a Django frontend and RabbitMQ server.
#
class zulip_ops::app_frontend_monitoring {
  include zulip_ops::prometheus::rabbitmq
  include zulip_ops::prometheus::uwsgi
  include zulip_ops::prometheus::process
  zulip_ops::firewall_allow { 'grok_exporter': port => '9144' }
  include zulip_ops::munin_node
  $munin_plugins = [
    'rabbitmq_connections',
    'rabbitmq_consumers',
    'rabbitmq_messages',
    'rabbitmq_messages_unacknowledged',
    'rabbitmq_messages_uncommitted',
    'rabbitmq_queue_memory',
    'zulip_send_receive_timing',
  ]
  zulip_ops::munin_plugin { $munin_plugins: }

  file { '/etc/cron.d/rabbitmq-monitoring':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/rabbitmq-monitoring',
  }
}
