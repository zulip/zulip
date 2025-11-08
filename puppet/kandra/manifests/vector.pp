# @summary Installs Vector to transform Prometheus data
#
class kandra::vector {
  $version = $zulip::common::versions['vector']['version']
  $dir = "/srv/zulip-vector-${version}"
  $bin = "${dir}/bin/vector"
  $conf = '/etc/vector.toml'

  $arch = $facts['os']['architecture'] ? {
    'amd64'   => 'x86_64',
    'aarch64' => 'aarch64',
  }

  zulip::external_dep { 'vector':
    version        => $version,
    url            => "https://packages.timber.io/vector/${version}/vector-${version}-${arch}-unknown-linux-gnu.tar.gz",
    tarball_prefix => "vector-${arch}-unknown-linux-gnu",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }
  file { "${zulip::common::supervisor_conf_dir}/vector.conf":
    ensure  => file,
    require => [
      User[zulip],
      Package[supervisor],
      Concat[$conf],
      File[$bin],
    ],
    before  => Exec['Cleanup vector'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/vector.conf.template.erb'),
    notify  => Service[supervisor],
  }

  exec { 'reload vector':
    command     => 'supervisorctl signal HUP vector',
    require     => Service[supervisor],
    refreshonly => true,
  }
  concat { $conf:
    ensure => present,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    notify => Exec['reload vector'],
  }
  # All of the pipelines need to be included in the Prometheus
  # exporter; they insert their strings at order 90, with a leading
  # comma, in the middle of the "inputs" block
  $vector_export = @(VECTOR)
    [sources.vector_metrics]
      type = "internal_metrics"
    [sinks.prometheus_exporter]
      type = "prometheus_exporter"
      address = "0.0.0.0:9081"
      flush_period_secs = 120
      suppress_timestamp = true
      buckets = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5]
      inputs = ["vector_metrics"
    |-VECTOR
  concat::fragment { 'vector_export_prefix':
    target  => $conf,
    content => $vector_export,
    order   => '89',
  }
  concat::fragment { 'vector_export_suffix':
    target  => $conf,
    content => "]\n",
    order   => '99',
  }
}
