# @summary Returns Prometheus scrape targets based on Teleport apps
#
# Only one instance is necessary.
#
class kandra::teleport::sd {
  include zulip::supervisor
  include kandra::teleport::tbot

  $version = $zulip::common::versions['teleport-sd']['version']
  $bin = "/srv/zulip-teleport-sd-${version}"

  zulip::external_dep { 'teleport-sd':
    version       => $version,
    url           => "https://github.com/alexmv/teleport-sd/releases/download/v${version}/teleport-sd-linux-${zulip::common::goarch}",
    cleanup_after => [Service[supervisor]],
  }

  file { "${zulip::common::supervisor_conf_dir}/teleport-sd.conf":
    ensure  => file,
    require => [
      Package[teleport],
      Package[supervisor],
      File[$bin],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/teleport-sd.conf.erb'),
    notify  => Service[supervisor],
  }
}
