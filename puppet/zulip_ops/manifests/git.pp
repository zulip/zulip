class zulip_ops::git {
  include zulip_ops::base

  $git_packages = [ ]
  package { $git_packages: ensure => 'installed' }

  file { '/home/git/repositories/eng/zulip.git/hooks':
    ensure => 'directory',
    owner  => 'git',
    group  => 'git',
    mode   => '0755',
  }

  file { '/home/git/repositories/eng/zulip.git/hooks/post-receive':
    ensure => 'link',
    target => '/home/zulip/zulip/tools/post-receive',
  }
}
