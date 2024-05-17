# @summary Observability using Grafana
#
class kandra::profile::grafana inherits kandra::profile::base {

  include zulip::supervisor

  $version = $zulip::common::versions['grafana']['version']
  $dir = "/srv/zulip-grafana-${version}"
  $bin = "${dir}/bin/grafana-server"
  $data_dir = '/var/lib/grafana'

  zulip::external_dep { 'grafana':
    version        => $version,
    url            => "https://dl.grafana.com/oss/release/grafana-${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "grafana-v${version}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  group { 'grafana':
    ensure => present,
    gid    => '1070',
  }
  user { 'grafana':
    ensure     => present,
    uid        => '1070',
    gid        => '1070',
    shell      => '/bin/bash',
    home       => $data_dir,
    managehome => false,
  }
  file { $data_dir:
    ensure  => directory,
    owner   => 'grafana',
    group   => 'grafana',
    require => [ User[grafana], Group[grafana] ],
  }
  file { '/var/log/grafana':
    ensure => directory,
    owner  => 'grafana',
    group  => 'grafana',
  }

  kandra::teleport::application { 'monitoring': port => '3000' }
  kandra::firewall_allow { 'grafana': port => '3000' }
  file { "${zulip::common::supervisor_conf_dir}/grafana.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      File[$bin],
      File[$data_dir],
      File['/var/log/grafana'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/supervisor/conf.d/grafana.conf.erb'),
    notify  => Service[supervisor],
  }

  $email_host = zulipconf('grafana', 'email_host', '')
  $email_from = zulipconf('grafana', 'email_from', '')
  $email_user = zulipsecret('secrets', 'grafana_email_user', '')
  $email_password = zulipsecret('secrets', 'grafana_email_password', '')
  file { '/etc/grafana':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  file { '/etc/grafana/grafana.ini':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/grafana.ini.template.erb'),
    notify  => Service[supervisor],
  }
}
