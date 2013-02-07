class humbug::rabbit {
  $rabbit_packages = [ "rabbitmq-server" ]
  package { $rabbit_packages: ensure => "installed" }

  # TODO: Should also call exactly once "servers/configure-rabbitmq"
}
