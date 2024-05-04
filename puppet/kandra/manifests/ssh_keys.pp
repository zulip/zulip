define kandra::ssh_keys(
  $keys = true,
) {
  $user = $name
  if $keys == true {
    $keypath = "prod/ssh/keys/${user}"
  } else {
    $keypath = "prod/ssh/keys/${keys}"
  }
  exec { "ssh_keys ${user}":
    require => File['/usr/local/bin/install-ssh-keys'],
    command => "/usr/local/bin/install-ssh-keys ${user} ${keypath}",
    unless  => "[ -f /usr/local/bin/install-ssh-keys ] && /usr/local/bin/install-ssh-keys ${user} ${keypath} check",
  }
}
