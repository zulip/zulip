class kandra::ksplice_uptrack {
  $ksplice_access_key = zulipsecret('secrets', 'ksplice_access_key', '')
  if $ksplice_access_key != '' {
    file { '/etc/uptrack':
      ensure => directory,
      owner  => 'root',
      group  => 'root',
      mode   => '0755',
    }
    file { '/etc/uptrack/uptrack.conf':
      ensure  => file,
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      content => template('kandra/uptrack/uptrack.conf.erb'),
    }
    $setup_apt_repo_file = "${facts['zulip_scripts_path']}/lib/setup-apt-repo"
    exec{ 'setup-apt-repo-ksplice':
      command => "${setup_apt_repo_file} --list ksplice",
      unless  => "${setup_apt_repo_file} --list ksplice --verify",
    }
    Package { 'uptrack':
      require => [
        Exec['setup-apt-repo-ksplice'],
        File['/etc/uptrack/uptrack.conf'],
      ],
    }
  } else {
    warning('No ksplice uptrack key is configured; ksplice is not installed!')
  }
}
