class zulip::postgres_common {
  $postgres_packages = [ "postgresql-9.1", "pgtune",
                         "python-argparse", "python-gevent",
                         "python-tz",
                         "lzop", "pv", "hunspell-en-us", "python-dateutil"]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $postgres_packages: ensure => "installed" }

  exec { "disable_logrotate":
    command => "/usr/bin/dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common",
    creates => '/etc/logrotate.d/postgresql-common.disabled',
  }
}
