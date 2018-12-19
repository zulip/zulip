class zulip::apache_sso {
  include zulip::localhost_sso

  case $::osfamily {
    'debian': {
      $apache_packages = [ 'apache2', 'libapache2-mod-wsgi-py3', ]
      $apache_former_packages = [ 'libapache2-mod-wsgi', ]
      $conf_dir = '/etc/apache2'
      $apache2 = 'apache2'
    }
    'redhat': {
      $apache_packages = [ 'httpd', 'python36u-mod_wsgi', ]
      $apache_former_packages = []
      $conf_dir = '/etc/httpd'
      $apache2 = 'httpd'
    }
    default: {
      fail('osfamily not supported')
    }
  }
  package { $apache_packages: ensure => 'installed' }
  package { $apache_former_packages: ensure => 'absent' }

  apache2mod { [ 'headers', 'proxy', 'proxy_http', 'rewrite', 'ssl', 'wsgi', ]:
    ensure  => present,
    require => Package[$apache2],
  }

  file { "${conf_dir}/ports.conf":
    ensure  => file,
    require => Package[$apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/zulip/apache/ports.conf',
  }

  file { "${conf_dir}/sites-available/":
    recurse => true,
    require => Package[$apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/zulip/apache/sites/',
  }
}
