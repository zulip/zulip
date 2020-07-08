define zulip_ops::munin_plugin {
  file { "/usr/local/munin/lib/plugins/${title}":
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => "puppet:///modules/zulip_ops/munin-plugins/${title}",
  }

  file { "/etc/munin/plugins/${name}":
    ensure  => 'link',
    require => File["/usr/local/munin/lib/plugins/${title}"],
    target  => "/usr/local/munin/lib/plugins/${title}",
    notify  => Service['munin-node'],
  }
}
