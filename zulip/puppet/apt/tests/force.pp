# force.pp
# force a package from a specific release

apt::force { 'package':
  release => 'testing',
  version => false
}
