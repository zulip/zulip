class zulip::zmirror_personals {
  class { 'zulip::base': }
  class { 'zulip::supervisor': }

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
  file { ['/home/humbug/api-keys', '/home/humbug/zephyr_sessions', '/home/humbug/ccache']:
    ensure     => directory,
    mode       => 644,
    owner      => "humbug",
    group      => "humbug",
  }

  # TODO: Do the rest of our setup, which includes at least:
  # Building patched libzephyr4-krb5 from davidben's roost branch and installing that
  #  (to add ZLoadSession/ZDumpSession).
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  #  (patched with tabbott's branch to add dump_session and load_session using the above)
}
