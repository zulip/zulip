class kandra::profile::prod_app_frontend inherits kandra::profile::base {
  include kandra::app_frontend
  include zulip::hooks::zulip_notify

  Kandra::User_Dotfiles['root'] {
    keys => 'internal-limited-write-deploy-key',
  }
  Kandra::User_Dotfiles['zulip'] {
    keys => 'internal-limited-write-deploy-key',
  }

  zulip::sysctl { 'conntrack':
    comment => 'Increase conntrack kernel table size',
    key     => 'net.nf_conntrack_max',
    value   => zulipconf('application_server', 'conntrack_max', 262144),
  }

  file { '/etc/nginx/sites-available/zulip':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/kandra/nginx/sites-available/zulip',
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/zulip':
    ensure  => link,
    require => Package['nginx-full'],
    target  => '/etc/nginx/sites-available/zulip',
    notify  => Service['nginx'],
  }

  # Prod has our Apple Push Notifications Service private key at
  # /etc/ssl/django-private/apns-dist.pem
}
