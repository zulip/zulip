# This class includes all the modules you need to install/run a Zulip installation
# in a single container (without the database, memcached, redis services).
# The database, memcached, redis services need to be run in seperate containers.
# Through this split of services, it is easier to scale the services to the needs.
class zulip::dockervoyager {
  include zulip::base
  # zulip::apt_repository must come after zulip::base
  include zulip::apt_repository
  include zulip::app_frontend

  $ignoreSupervisorService = true

  include zulip::supervisor

  file { "/etc/supervisor/conf.d/cron.conf":
    ensure  => file,
    require => Package[supervisor],
    owner   => "root",
    group   => "root",
    mode    => "0644",
    source  => "puppet:///modules/zulip/supervisor/conf.d/cron.conf",
  }
  file { "/etc/supervisor/conf.d/nginx.conf":
    ensure  => file,
    require => Package[supervisor],
    owner   => "root",
    group   => "root",
    mode    => "0644",
    source  => "puppet:///modules/zulip/supervisor/conf.d/nginx.conf",
  }
}
