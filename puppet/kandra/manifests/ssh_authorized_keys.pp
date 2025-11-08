define kandra::ssh_authorized_keys(
  $keys = true,
) {
  $user = $name
  if $keys == true {
    $keypath = "prod/ssh/authorized_keys/${user}"
  } elsif $keys.is_a(Array) {
    $keypath = join($keys.map |$k| {"prod/ssh/authorized_keys/${k}"}, ' ')
  } else {
    $keypath = "prod/ssh/authorized_keys/${keys}"
  }
  exec { "ssh_authorized_keys ${user}":
    require => File['/usr/local/bin/install-ssh-authorized-keys'],
    command => "/usr/local/bin/install-ssh-authorized-keys ${user} ${keypath}",
    unless  => "[ -f /usr/local/bin/install-ssh-authorized-keys ] && /usr/local/bin/install-ssh-authorized-keys --check ${user} ${keypath}",
  }
}
