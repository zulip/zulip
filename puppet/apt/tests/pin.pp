# pin a release in apt, useful for unstable repositories
apt::pin { 'foo':
  packages => '*',
  priority => 0,
}
