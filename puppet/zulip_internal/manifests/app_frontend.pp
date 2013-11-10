class zulip_internal::app_frontend {
  include zulip::app_frontend
  $app_packages = [# Needed for minify-js
                   "yui-compressor",
                   "nodejs",
                   # Needed for statsd reporting
                   "python-django-statsd-mozilla",
                   ]
  package { $app_packages: ensure => "installed" }

}
