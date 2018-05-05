class zulip::static_asset_compiler {
  if $zulip::base::release_name == 'trusty' {
    $closure_compiler_package = 'libclosure-compiler-java'
  } else {
    $closure_compiler_package = 'closure-compiler'
  }
  $static_asset_compiler_packages = [
    # Needed for minify-js
    $closure_compiler_package,
    'nodejs',
    'nodejs-legacy',
    'yui-compressor',
    # Used by makemessages i18n
    'gettext',
  ]

  safepackage { $static_asset_compiler_packages: ensure => 'installed' }
}
