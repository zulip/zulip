# Puppet profile for managing a LiveKit server instance.
#
# Reads configuration from zulip.conf [livekit] section and
# secrets from zulip-secrets.conf.
class zulip::profile::livekit {
  include zulip::profile::base

  $version = $zulip::common::versions['livekit-server']['version']
  $bin = "/srv/zulip-livekit-server-${version}"

  zulip::external_dep { 'livekit-server':
    version        => $version,
    url            => "https://github.com/livekit/livekit/releases/download/v${version}/livekit_${version}_linux_${zulip::common::goarch}.tar.gz",
    tarball_prefix => 'livekit-server',
  }

  $livekit_port = zulipconf('livekit', 'port', 7880)
  $livekit_rtc_tcp_port = zulipconf('livekit', 'rtc_tcp_port', 7881)
  $livekit_rtc_udp_port_start = zulipconf('livekit', 'rtc_udp_port_start', 50000)
  $livekit_rtc_udp_port_end = zulipconf('livekit', 'rtc_udp_port_end', 60000)
  $livekit_api_key = zulipsecret('secrets', 'livekit_api_key', '')
  $livekit_api_secret = zulipsecret('secrets', 'livekit_api_secret', '')

  file { '/etc/livekit.yaml':
    ensure  => file,
    require => File[$bin],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    content => template('zulip/livekit.yaml.template.erb'),
    notify  => Service['livekit-server'],
  }

  file { '/etc/systemd/system/livekit-server.service':
    ensure  => file,
    require => File[$bin],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/livekit-server.service.template.erb'),
    notify  => Service['livekit-server'],
  }

  service { 'livekit-server':
    ensure    => running,
    enable    => true,
    require   => File['/etc/livekit.yaml', '/etc/systemd/system/livekit-server.service'],
    subscribe => File['/etc/livekit.yaml'],
  }
}
