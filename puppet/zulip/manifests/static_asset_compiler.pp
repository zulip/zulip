class zulip::static_asset_compiler {
  if $zulip::base::release_name == "trusty" {
    $closure_compiler_package = "libclosure-compiler-java"
  } elsif $zulip::base::release_name == "xenial" {
    $closure_compiler_package = "closure-compiler"
  }
  $static_asset_compiler_packages = [
                                     # Needed for minify-js
                                     $closure_compiler_package,
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
