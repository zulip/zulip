class zulip_ops::ksplice_uptrack {
  file { '/etc/uptrack':
    ensure => 'directory',
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  $ksplice_access_key = zulipsecret('secrets','ksplice_access_key','')
  file { '/etc/uptrack/uptrack.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/uptrack/uptrack.conf.erb'),
  }
  $setup_apt_repo_file = "${::zulip_scripts_path}/lib/setup-apt-repo-ksplice"
  exec{ 'setup-apt-repo-ksplice':
    command => $setup_apt_repo_file,
    unless  => "${setup_apt_repo_file} --verify",
  }
  Package { 'uptrack':
    require => [
      Exec['setup-apt-repo-ksplice'],
      File['/etc/uptrack/uptrack.conf'],
    ],
  }
}
