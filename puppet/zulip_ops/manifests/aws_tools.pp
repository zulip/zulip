# @summary Installs the AWS CLI
#
class zulip_ops::aws_tools {
  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'

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

  if ! $is_ec2 {
    if $::os['architecture'] != 'amd64' {
      # We would need to build aws_signing_helper from source
      fail('Only amd64 hosts supported on non-EC2')
    }
    $helper_version = $zulip::common::versions['aws_signing_helper']['version']
    zulip::external_dep { 'aws_signing_helper':
      version => $helper_version,
      url     => "https://rolesanywhere.amazonaws.com/releases/${helper_version}/X86_64/Linux/aws_signing_helper",
      before  => File['/root/.aws/config'],
    }
    file { '/srv/zulip-aws-tools/bin/aws_signing_helper':
      ensure  => link,
      target  => "/srv/zulip-aws_signing_helper-${helper_version}",
      require => [
        Zulip::External_Dep['aws_signing_helper'],
        Exec['install-aws-cli'],
      ],
    }
    package { 'sqlite3': ensure => installed }
    file { '/usr/local/bin/teleport-aws-credentials':
      ensure  => file,
      require => [
        Package['sqlite3'],
        Service['teleport_node'],
      ],
      before  => [
        File['/root/.aws/config'],
      ],
      mode    => '0755',
      owner   => 'root',
      group   => 'root',
      source  => 'puppet:///modules/zulip_ops/teleport-aws-credentials',
    }
  }
  file { '/root/.aws':
    ensure => directory,
    mode   => '0755',
    owner  => 'root',
    group  => 'root',
  }
  $aws_trust_arn = zulipsecret('secrets','aws_trust_arn','')
  $aws_profile_arn = zulipsecret('secrets','aws_profile_arn','')
  $aws_role_arn = zulipsecret('secrets','aws_role_arn','')
  file { '/root/.aws/config':
    ensure  => file,
    mode    => '0644',
    owner   => 'root',
    group   => 'root',
    content => template('zulip_ops/dotfiles/aws_config.erb'),
  }
}
