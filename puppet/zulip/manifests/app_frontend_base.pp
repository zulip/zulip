# Minimal configuration to run a Zulip application server.
# Default nginx configuration is included in extension app_frontend.pp.
class zulip::app_frontend_base {
  include zulip::nginx
  include zulip::supervisor

  $web_packages = [ # Needed for memcached usage
                    "python-pylibmc",
                    # Fast JSON parser
                    "python-ujson",
                    # Django dependencies
                    "python-django",
                    "python-django-guardian",
                    "python-django-pipeline",
                    "python-django-bitfield",
                    # Needed for mock objects in decorators
                    "python-mock",
                    # Tornado dependencies
                    "python-tornado",
                    "python-sockjs-tornado",
                    # Needed for our fastcgi setup
                    "python-flup",
                    # Needed for markdown processing
                    "python-markdown",
                    "python-pygments",
                    # Used for Hesiod lookups, etc.
                    "python-dns",
                    # Needed to access our database
                    "postgresql-client-${zulip::base::postgres_version}",
                    "python-psycopg2",
                    # Needed for building complex DB queries
                    "python-sqlalchemy",
                    # Needed for integrations
                    "python-twitter",
                    "python-defusedxml",
                    # Needed for the email mirror
                    "python-twisted",
                    "python-html2text",
                    # Needed to access rabbitmq
                    "python-pika",
                    # Needed for timezone work
                    "python-tz",
                    # Needed to parse source maps for error reporting
                    "python-sourcemap",
                    # Needed for redis
                    "python-redis",
                    # Needed for S3 file uploads
                    "python-boto",
                    # Needed to send email
                    "python-mandrill",
                    # Needed to generate diffs for edits
                    "python-diff-match-patch",
                    # Needed for iOS
                    "python-apns-client",
                    # Needed for Android push
                    "python-gcm-client",
                    # Needed for avatar image resizing
                    "python-imaging",
                    # Needed for LDAP support
                    "python-django-auth-ldap",
                    # Needed for Google Apps mobile auth
                    "python-googleapi",
                    # Needed for JWT-based auth
                    "python-pyjwt",
                    ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $web_packages: ensure => "installed" }

  file { "/etc/nginx/zulip-include/app":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/app",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/upstreams":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/upstreams",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/uploads.types":
    require => Package["nginx-full"],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-frontend/uploads.types",
    notify => Service["nginx"],
  }
  file { "/etc/nginx/zulip-include/app.d/":
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 755,
  }
  file { "/etc/supervisor/conf.d/zulip.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisor/conf.d/zulip.conf",
    notify => Service["supervisor"],
  }
  file { "/home/zulip/tornado":
    ensure => directory,
    owner => "zulip",
    group => "zulip",
    mode => 755,
  }
  file { '/home/zulip/logs':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/home/zulip/prod-static':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/home/zulip/deployments':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { "/etc/cron.d/email-mirror":
    ensure => absent,
  }
}
