# This is a simple smoke test
# of the file_line resource type.
file { '/tmp/dansfile':
  ensure => present
}->
file_line { 'dans_line':
  line => 'dan is awesome',
  path => '/tmp/dansfile',
}
