class zulip::auto_saml_configuration {
  # Currently: update the IdP's SAML certificates daily.
  file { '/etc/cron.d/auto-saml-configuration':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/auto-saml-configuration',
  }
}
