
define zulip::cron(
  String $minute,
  String $hour = '*',
  String $dow = '*',
  String $user = 'zulip',
  Optional[String] $command = undef,
  Optional[String] $manage = undef,
) {
  if $command != undef {
    $run = $command
  } elsif $manage != undef {
    $run = "cd /home/zulip/deployments/current/ && ./manage.py ${manage} >/dev/null"
  } else {
    $underscores = regsubst($title, '-', '_', 'G')
    $run = "cd /home/zulip/deployments/current/ && ./manage.py ${underscores} >/dev/null"
  }
  file { "/etc/cron.d/${title}":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/cron.template.erb'),
  }
}
