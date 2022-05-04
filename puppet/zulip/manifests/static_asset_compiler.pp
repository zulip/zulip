class zulip::static_asset_compiler {
  case $::os['family'] {
    'Debian': {
      $static_asset_compiler_packages = [
        # Used by makemessages i18n
        'gettext',
      ]
    }
    'RedHat': {
      $static_asset_compiler_packages = [
        'gettext',
      ]
    }
    default: {
      fail('osfamily not supported')
    }
  }

  zulip::safepackage { $static_asset_compiler_packages: ensure => installed }
}
