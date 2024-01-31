define zulip_ops::user_dotfiles (
  $home = '',
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
    source  => 'puppet:///modules/zulip_ops/dotfiles/emacs.el',
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
}
