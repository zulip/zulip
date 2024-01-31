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
}
