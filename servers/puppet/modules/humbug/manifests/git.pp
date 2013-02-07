class humbug::git {
  class { 'humbug::base': }

  $git_packages = [ ]
  package { $git_packages: ensure => "installed" }

  # TODO: Should confirm git repos at /srv/git and then setup
  # /srv/git/humbug.git/hooks/post-receive ->
  # /home/humbug/humbug/tools/post-receive
}
