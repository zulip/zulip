# This class includes all the modules you need to install/run a Zulip installation
# in a single container (without the database, memcached, redis services).
# The database, memcached, redis services need to be run in seperate containers.
# Through this split of services, it is easier to scale the services to the needs.
class zulip::dockervoyager {
  include zulip::base
  # zulip::apt_repository must come after zulip::base
  include zulip::apt_repository
  include zulip::app_frontend
  include zulip::supervisor
  include zulip::process_fts_updates
  include zulip::thumbor

  file { "${zulip::common::supervisor_conf_dir}/cron.conf":
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/cron.conf',
  }
  file { "${zulip::common::supervisor_conf_dir}/nginx.conf":
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/nginx.conf',
  }
}
