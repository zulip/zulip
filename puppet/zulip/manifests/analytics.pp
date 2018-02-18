# Default configuration for a Zulip app frontend
# This should only be enabled on exactly 1 Zulip server in a cluster.
class zulip::analytics {
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
}
