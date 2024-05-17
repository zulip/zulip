class kandra::profile::zmirror_personals inherits kandra::profile::base {

  include zulip::supervisor

  Kandra::User_Dotfiles['zulip'] {
    authorized_keys => [
      'common',
      'production-write-ccache',
    ],
  }

  $zmirror_packages = [ # Packages needed to run the mirror
    'libzephyr4-krb5',
    'zephyr-clients',
    'krb5-config',
    'krb5-user',
    # Packages needed to for ctypes access to Zephyr
    'python3-dev',
    'python3-typing-extensions',
    'restricted-ssh-commands',
  ]
  package { $zmirror_packages:
    ensure => installed,
  }

  # The production-write-ccache key uses
  # `command="/usr/lib/restricted-ssh-commands"` which allows us to
  # limit the commands it can run.
  file { '/etc/restricted-ssh-commands':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  file { '/etc/restricted-ssh-commands/zulip':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => join([
      '^/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache ',
      '[a-z0-9_.-]+ ',
      '[A-Za-z0-9]{32} ',
      '[-A-Za-z0-9+/]*={0,3}$',
      "\n",
    ], ''),
  }

  file { '/etc/krb5.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/kandra/krb5.conf',
  }

  concat::fragment { '01-supervisor-zmirror':
    order   => '10',
    target  => $zulip::common::supervisor_conf_file,
    content => " ${zulip::common::supervisor_system_conf_dir}/zmirror/*.conf",
  }

  file { ['/home/zulip/api-keys', '/home/zulip/zephyr_sessions', '/home/zulip/ccache',
          '/home/zulip/mirror_status', "${zulip::common::supervisor_system_conf_dir}/zmirror"]:
    ensure => directory,
    mode   => '0755',
    owner  => 'zulip',
    group  => 'zulip',
  }

  file { '/etc/cron.d/test_zephyr_personal_mirrors':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/kandra/cron.d/test_zephyr_personal_mirrors',
  }

  file { '/usr/lib/nagios/plugins/zulip_zephyr_mirror':
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/kandra/nagios_plugins/zulip_zephyr_mirror',
  }

  # Allow the relevant UDP ports
  concat::fragment { 'iptables-zmirror.v4':
    target => '/etc/iptables/rules.v4',
    source => 'puppet:///modules/kandra/iptables/zmirror.v4',
    order  => '20',
  }
  concat::fragment { 'iptables-zmirror.v6':
    target => '/etc/iptables/rules.v6',
    source => 'puppet:///modules/kandra/iptables/zmirror.v6',
    order  => '20',
  }
}
