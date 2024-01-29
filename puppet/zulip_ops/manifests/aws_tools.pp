# @summary Installs the AWS CLI
#
class zulip_ops::aws_tools {
  file { '/usr/local/bin/install-aws-cli':
    ensure => file,
    mode   => '0755',
    source => 'puppet:///modules/zulip_ops/install-aws-cli',
  }
  exec { 'install-aws-cli':
    require => File['/usr/local/bin/install-aws-cli'],
    command => '/usr/local/bin/install-aws-cli',
    # When puppet is initially determining which resources need to be
    # applied, it will call the unless -- but install-aws-cli may not
    # exist yet.  Count this as needing to run.
    unless  => '[ -f /usr/local/bin/install-aws-cli ] && /usr/local/bin/install-aws-cli check',
  }
}
