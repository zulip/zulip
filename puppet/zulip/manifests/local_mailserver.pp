class zulip::local_mailserver {
  include zulip::snakeoil
  include zulip::certbot

  if zulipconf('postfix', 'uninstall', true) {
    package { 'postfix':
      # TODO/compatibility: We can remove this when upgrading directly
      # from 10.x is no longer possible.  We do not use "purged" here,
      # since that would remove config files, which users may have had
      # installed.
      ensure => absent,
      before => Service[$zulip::common::supervisor_service],
    }
  }
  file { "${zulip::common::supervisor_conf_dir}/email-mirror.conf":
    ensure  => file,
    require => [
      Package[supervisor],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/email-mirror.conf.template.erb'),
    notify  => Service[$zulip::common::supervisor_service],
  }
  file { '/etc/letsencrypt/renewal-hooks/deploy/055-email-server.sh':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/zulip/letsencrypt/055-email-server.sh',
  }
}
