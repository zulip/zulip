# @summary Export Weblate translation stats
class kandra::prometheus::weblate {
  include kandra::prometheus::base
  include zulip::supervisor

  # We embed the hash of the contents into the name of the process, so
  # that `supervisorctl reread` knows that it has updated.
  $full_exporter_hash = sha256(file('kandra/weblate_exporter'))
  $exporter_hash = $full_exporter_hash[0,8]

  $bin = '/usr/local/bin/weblate_exporter'
  file { $bin:
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/kandra/weblate_exporter',
  }

  file { "${zulip::common::supervisor_conf_dir}/weblate_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/weblate_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }

  include kandra::prometheus::pushgateway
  zulip::cron { 'weblate-to-pushgateway':
    minute    => '*/15',
    command   => 'curl http://localhost:9189/metrics | curl --data-binary @- http://localhost:9091/metrics/job/weblate',
    use_proxy => false,
  }
}
