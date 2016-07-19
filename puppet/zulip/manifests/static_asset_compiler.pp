class zulip::static_asset_compiler {
  $static_asset_compiler_packages = [
                                     # Needed for minify-js
                                     "closure-compiler",
                                     "nodejs",
                                     "nodejs-legacy",
                                     "npm",
                                     "yui-compressor",
                                     # Used by makemessages i18n
                                     "gettext",
                                     ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $static_asset_compiler_packages: ensure => "installed" }
}
