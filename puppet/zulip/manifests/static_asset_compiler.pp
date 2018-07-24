class zulip::static_asset_compiler {
  $static_asset_compiler_packages = [
    # Needed for minifying js
    'yui-compressor',
    # Used by makemessages i18n
    'gettext',
  ]

  safepackage { $static_asset_compiler_packages: ensure => 'installed' }
}
