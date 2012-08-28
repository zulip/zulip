# This class includes all the modules you need to install/run a Zulip installation
# in a single container (without the database, memcached, Redis services).
# The database, memcached, Redis services need to be run in separate containers.
# Through this split of services, it is easier to scale the services to the needs.
class zulip::profile::docker {
  include zulip::profile::base
  include zulip::profile::app_frontend
  include zulip::localhost_camo
  include zulip::local_mailserver
  include zulip::supervisor
  include zulip::process_fts_updates

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
