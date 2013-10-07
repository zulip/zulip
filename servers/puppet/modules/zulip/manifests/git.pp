class zulip::git {
  class { 'zulip::base': }

  $git_packages = [ ]
  package { $git_packages: ensure => "installed" }

  file { '/home/git/repositories/eng/zulip.git/hooks':
    ensure => 'directory',
    owner  => 'git',
    group  => 'git',
    mode   => 755,
  }

  file { '/home/git/repositories/eng/zulip.git/hooks/post-receive':
    ensure => 'link',
    target => '/home/humbug/humbug/tools/post-receive',
  }
}
