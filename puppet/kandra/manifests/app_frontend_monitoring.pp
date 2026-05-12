# @summary Prometheus monitoring of a Django frontend and RabbitMQ server.
#
class kandra::app_frontend_monitoring {
  include kandra::prometheus::memcached
  include kandra::prometheus::rabbitmq
  include kandra::prometheus::uwsgi
  include kandra::prometheus::process
  include kandra::prometheus::grok
  kandra::teleport::prometheus_app { 'tusd': port => '9900' }
  kandra::teleport::prometheus_app { 'katex': port => '9700' }

  file { '/etc/cron.d/rabbitmq-monitoring':
    ensure => absent,
  }
  zulip::cron { 'check-rabbitmq-queue':
    minute  => '*',
    user    => 'root',
    command => '/home/zulip/deployments/current/scripts/nagios/check-rabbitmq-queue',
  }
  zulip::cron { 'check-rabbitmq-consumers':
    minute  => '*',
    user    => 'root',
    command => '/home/zulip/deployments/current/scripts/nagios/check-rabbitmq-consumers',
  }
}
