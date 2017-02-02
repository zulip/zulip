# Default configuration for a Zulip app frontend
class zulip::analytics {
  # This should only be enabled on exactly 1 Zulip server in a cluster.
  file { "/etc/cron.d/update-analytics-counts":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/update-analytics-counts",
  }
}
