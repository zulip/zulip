class humbug::zmirror {
  class { 'humbug::base': }

  $zmirror_packages = [ "cython", "libzephyr-dev", "comerr-dev", "python-dev", "libzephyr4-krb5", "zephyr-clients",
                        "krb5-config", "krb5-user", "krb5-clients"]
  package { $zmirror_packages: ensure => "installed" }

  # TODO: Do the rest of our setup, which includes at least:
  # Configuring Kerberos and Zephyr for the MIT realm
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  # Putting tabbott/extra's keytab on the system at /home/humbug/tabbott.extra.keytab
  # Setting api/bots/zephyr-mirror-crontab to be the Humbug user's crontab
  # Running the mirroring bot in a screen session with these arguments:
  # /home/humbug/api/bots/zephyr_mirror.py --root-path=/home/humbug/ --user=tabbott/extra --enable-log=/home/humbug/all_zephyrs_log --forward-class-messages
}
