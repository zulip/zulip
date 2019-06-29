class zulip::static_asset_compiler {
  include zulip::common
  case $::osfamily {
    'debian': {
      $static_asset_compiler_packages = [
        'yui-compressor',
        # Used by makemessages i18n
        'gettext',
      ]
    }
    'redhat': {
      $static_asset_compiler_packages = [
        'yuicompressor',
        'gettext',
      ]
    }
    default: {
      fail('osfamily not supported')
    }
  }

  zulip::safepackage { $static_asset_compiler_packages: ensure => 'installed' }
}
