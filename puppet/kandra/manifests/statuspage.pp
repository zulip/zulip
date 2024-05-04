# @summary Plumb Prometheus stats into status.zulip.com
#
# Requires a /etc/zulip/statuspage.conf which maps statuspage.io
# metric_ids to Prometheus queries.
class kandra::statuspage {
  $bin = '/usr/local/bin/statuspage-pusher'

  file { $bin:
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/kandra/statuspage-pusher',
  }

  file { "${zulip::common::supervisor_conf_dir}/statuspage-pusher.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/statuspage-pusher.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
