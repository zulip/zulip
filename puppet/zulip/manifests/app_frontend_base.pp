# Minimal configuration to run a Zulip application server.
# Default nginx configuration is included in extension app_frontend.pp.
class zulip::app_frontend_base {
  include zulip::nginx
  include zulip::supervisor

  $web_packages = [
                    # Needed to access our database
                    "postgresql-client-${zulip::base::postgres_version}",
                    ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $web_packages: ensure => "installed" }

  file { "/etc/nginx/zulip-include/app":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/app",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/upstreams":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/upstreams",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/uploads.types":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/uploads.types",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/app.d/":
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 755,
  }

  $loadbalancers = split(zulipconf("loadbalancer", "ips", ""), ",")
  if $loadbalancers != [] {
    file { "/etc/nginx/zulip-include/app.d/accept-loadbalancer.conf":
      require => File["/etc/nginx/zulip-include/app.d"],
      owner  => "root",
      group  => "root",
      mode => 644,
      content => template("zulip/accept-loadbalancer.conf.template.erb"),
      notify => Service["nginx"],
    }
  }

  # This determines whether we run queue processors multithreaded or
  # multiprocess.  Multiprocess scales much better, but requires more
  # RAM; we just auto-detect based on available system RAM.
  $queues_multiprocess = $::memorysize_mb > 3500
  $queues = $zulip::base::normal_queues
  if $queues_multiprocess {
    $message_sender_default_processes = 4
    $uwsgi_default_processes = 6
  } else {
    $message_sender_default_processes = 2
    $uwsgi_default_processes = 4
  }
  $message_sender_processes = zulipconf("application_server", "message_sender_processes",
                                        $message_sender_default_processes)
  file { "/etc/supervisor/conf.d/zulip.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    content => template("zulip/supervisor/zulip.conf.template.erb"),
    notify => Service["supervisor"],
  }

  $uwsgi_processes = zulipconf("application_server", "uwsgi_processes",
                               $uwsgi_default_processes)
  file { "/etc/zulip/uwsgi.ini":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    content => template("zulip/uwsgi.ini.template.erb"),
    notify => Service["supervisor"],
  }

  file { "/home/zulip/tornado":
    ensure => directory,
    owner => "zulip",
    group => "zulip",
    mode => 755,
  }
  file { '/home/zulip/logs':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/home/zulip/prod-static':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/home/zulip/deployments':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { "/srv/zulip-npm-cache":
    ensure => directory,
    owner => "zulip",
    group => "zulip",
    mode => 755,
  }
  file { "/srv/zulip-emoji-cache":
    ensure => directory,
    owner => "zulip",
    group => "zulip",
    mode => 755,
  }
  file { "/etc/cron.d/email-mirror":
    ensure => absent,
  }
  file { "/usr/lib/nagios/plugins/zulip_app_frontend":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => true,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip/nagios_plugins/zulip_app_frontend",
  }
}
