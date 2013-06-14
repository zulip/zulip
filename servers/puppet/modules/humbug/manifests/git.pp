class humbug::git {
  class { 'humbug::base': }

  # We run our wiki off of git.humbughq.com; this may change.
  class { 'humbug::wiki': }

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
