# @summary Install a cron file into /etc/cron.d
#
define zulip::cron(
  String $minute,
  String $hour = '*',
  String $dow = '*',
  String $user = 'zulip',
  Optional[String] $command = undef,
  Optional[String] $manage = undef,
) {
  $dsn = zulipconf('sentry', 'project_dsn', '')
  if $dsn != '' {
    include zulip::sentry_cli
    $environment = zulipconf('machine', 'deploy_type', 'development')
    $sentry = "sentry-cli monitors run -e ${environment} --schedule '${minute} ${hour} * * ${dow}' ${title} -- "
    $cron_require = [File['/usr/local/bin/sentry-cli']]
  } else {
    $sentry = ''
    $cron_require = []
  }
  if $command != undef {
    $run = $command
  } elsif $manage != undef {
    $run = "cd /home/zulip/deployments/current/ && ${sentry}./manage.py ${manage} >/dev/null"
  } else {
    $underscores = regsubst($title, '-', '_', 'G')
    $run = "cd /home/zulip/deployments/current/ && ${sentry}./manage.py ${underscores} >/dev/null"
  }
  file { "/etc/cron.d/${title}":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/cron.template.erb'),
    require => $cron_require,
  }
}
