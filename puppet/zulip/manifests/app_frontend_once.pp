# Cron jobs and other tools that should run on only one Zulip server
# in a cluster.

class zulip::app_frontend_once {
  file { "/etc/cron.d/send-digest-emails":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/send-digest-emails",
  }

  file { "/etc/cron.d/update-analytics-counts":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/update-analytics-counts",
  }

  file { "/etc/cron.d/check-analytics-state":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/check-analytics-state",
  }

  file { "/etc/cron.d/soft-deactivate-users":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/soft-deactivate-users",
  }

  file { "/etc/cron.d/calculate-first-visible-message-id":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/calculate-first-visible-message-id",
  }

  file { "/etc/cron.d/clearsessions":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/clearsessions",
  }
}
