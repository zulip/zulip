# @summary Prometheus monitoring of rabbitmq server.  This is done via
# the built-in prometheus plugin which serves on port 15692:
# https://www.rabbitmq.com/prometheus.html
#
class kandra::prometheus::rabbitmq {
  include kandra::prometheus::base

  exec { 'enable rabbitmq-prometheus':
    command => 'rabbitmq-plugins enable rabbitmq_prometheus',
    unless  => 'grep -q rabbitmq_prometheus /etc/rabbitmq/enabled_plugins',
    require => Service['rabbitmq-server'],
  }
  exec { 'enable rabbitmq-prometheus-per-metric':
    command => "rabbitmqctl eval 'application:set_env(rabbitmq_prometheus, return_per_object_metrics, true).'",
    unless  => @("EOT"),
      [ -f /usr/sbin/rabbitmqctl ] &&
      /usr/sbin/rabbitmqctl eval 'application:get_env(rabbitmq_prometheus, return_per_object_metrics).' \
        | grep -q true
      | EOT
    require => Exec['enable rabbitmq-prometheus'],
  }
  kandra::firewall_allow { 'rabbitmq': port => '15692' }
}
