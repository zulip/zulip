class zulip::git {
  class { 'zulip::base': }

  $git_packages = [ ]
  package { $git_packages: ensure => "installed" }

  file { '/srv/git/humbug.git':
    ensure => 'directory',
    owner  => 'humbug',
    group  => 'humbug',
    mode   => 755,
  }

  file { '/srv/git/humbug.git/hooks/post-receive':
    ensure => 'link',
    target => '/home/humbug/humbug/tools/post-receive',
  }
}
