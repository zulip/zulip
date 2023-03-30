# @summary Prometheus monitoring of uwsgi servers
#
class zulip_ops::prometheus::uwsgi {
  include zulip_ops::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['uwsgi_exporter']['version']
  $dir = "/srv/zulip-uwsgi_exporter-${version}"
  $bin = "${dir}/uwsgi_exporter"

  zulip::external_dep { 'uwsgi_exporter':
    version        => $version,
    url            => "https://github.com/timonwong/uwsgi_exporter/releases/download/v${version}/uwsgi_exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "uwsgi_exporter-${version}.linux-${zulip::common::goarch}",
  }

  zulip_ops::firewall_allow { 'uwsgi_exporter': port => '9238' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_uwsgi_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      Zulip::External_Dep['uwsgi_exporter'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/supervisor/conf.d/prometheus_uwsgi_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
