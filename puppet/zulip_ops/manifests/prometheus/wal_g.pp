# @summary Prometheus monitoring of wal-g backups
#
class zulip_ops::prometheus::wal_g {
  include zulip_ops::prometheus::base
  include zulip::supervisor
  include zulip::wal_g

  file { '/usr/local/bin/wal-g-exporter':
    ensure  => file,
    require => User[zulip],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/postgresql/wal-g-exporter',
  }

  # We embed the hash of the contents into the name of the process, so
  # that `supervisorctl reread` knows that it has updated.
  $full_exporter_hash = sha256(file('zulip/postgresql/wal-g-exporter'))
  $exporter_hash = $full_exporter_hash[0,8]
  file { "${zulip::common::supervisor_conf_dir}/prometheus_wal_g_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File['/usr/local/bin/wal-g-exporter'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_wal_g_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
