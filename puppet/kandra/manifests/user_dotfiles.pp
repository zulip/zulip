define kandra::user_dotfiles (
  $home = '',
  $keys = false,
  $authorized_keys = false,
  $known_hosts = false,
) {
  $user = $name

  if $home == '' {
    $homedir = "/home/${user}"
  } else {
    $homedir = $home
  }

  file { "${homedir}/.ssh":
    ensure  => directory,
    require => User[$user],
    owner   => $user,
    group   => $user,
    mode    => '0700',
  }

  file { "${homedir}/.emacs":
    ensure  => file,
    require => User[$user],
    owner   => $user,
    group   => $user,
    mode    => '0644',
    source  => 'puppet:///modules/kandra/dotfiles/emacs.el',
  }

  # Suppress MOTD printing, to fix load problems with Nagios caused by
  # Ubuntu's default MOTD tools for things like "checking for the next
  # release" being super slow.
  file { "${homedir}/.hushlogin":
    ensure  => file,
    require => User[$user],
    owner   => $user,
    group   => $user,
    mode    => '0644',
    content => '',
  }

  if $keys != false {
    kandra::ssh_keys{ $user:
      keys    => $keys,
      require => File["${homedir}/.ssh"],
    }
  }
  if $authorized_keys != false {
    kandra::ssh_authorized_keys{ $user:
      keys    => $authorized_keys,
      require => File["${homedir}/.ssh"],
    }
  }
  if $known_hosts != false {
    file { "${homedir}/.ssh/known_hosts":
      # We mark this as "present" to ensure that it exists, but not to
      # directly control its contents.
      ensure  => present,
      owner   => $user,
      group   => $user,
      mode    => '0644',
      require => File["${homedir}/.ssh"],
    }
    $known_hosts.each |Optional[String] $hostname| {
      if $hostname == undef {
        # pass
      } elsif $hostname == 'github.com' {
        $github_keys = file('kandra/github.keys')
        exec { "${user} ssh known_hosts ${hostname}":
          command => "echo '${github_keys}' >> ${homedir}/.ssh/known_hosts",
          unless  => "grep ${hostname} ${homedir}/.ssh/known_hosts",
          require => File["${homedir}/.ssh/known_hosts"],
        }
      } else {
        exec { "${user} ssh known_hosts ${hostname}":
          command => "ssh-keyscan ${hostname} >> ${homedir}/.ssh/known_hosts",
          unless  => "grep ${hostname} ${homedir}/.ssh/known_hosts",
          require => File["${homedir}/.ssh/known_hosts"],
        }
      }
    }
  }
}
