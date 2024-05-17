# @summary Prometheus monitoring of uwsgi servers
#
class kandra::prometheus::uwsgi {
  include kandra::prometheus::base
  include zulip::supervisor

  $version = $zulip::common::versions['uwsgi_exporter']['version']
  $dir = "/srv/zulip-uwsgi_exporter-${version}"
  $bin = "${dir}/uwsgi_exporter"

  zulip::external_dep { 'uwsgi_exporter':
    version        => $version,
    url            => "https://github.com/timonwong/uwsgi_exporter/releases/download/v${version}/uwsgi_exporter-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "uwsgi_exporter-${version}.linux-${zulip::common::goarch}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  kandra::firewall_allow { 'uwsgi_exporter': port => '9238' }
  file { "${zulip::common::supervisor_conf_dir}/prometheus_uwsgi_exporter.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/prometheus_uwsgi_exporter.conf.template.erb'),
    notify  => Service[supervisor],
  }
}
