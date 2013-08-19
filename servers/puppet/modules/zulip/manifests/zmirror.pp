class zulip::zmirror {
  class { 'zulip::base': }

  $zmirror_packages = [ "cython", "libzephyr-dev", "comerr-dev", "python-dev", "libzephyr4-krb5", "zephyr-clients",
                        "krb5-config", "krb5-user", "krb5-clients", "debathena-kerberos-config", "debathena-zephyr-config"]
  package { $zmirror_packages: ensure => "installed" }

  file { '/etc/apt/sources.list.d/debathena.list':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip/debathena.list',
  }

  # TODO: Do the rest of our setup, which includes at least:
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  # Putting tabbott/extra's keytab on the system at /home/humbug/tabbott.extra.keytab
  # Setting api/bots/zephyr-mirror-crontab to be the humbug user's crontab
  # Running the mirroring bot in a screen session with these arguments:
  # /home/humbug/api/bots/zephyr_mirror.py --root-path=/home/humbug/ --user=tabbott/extra --enable-log=/home/humbug/all_zephyrs_log --forward-class-messages
}
