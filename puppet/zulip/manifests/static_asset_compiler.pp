class zulip::static_asset_compiler {
  include zulip::common
  case $::osfamily {
    'debian': {
      if $zulip::base::release_name == 'trusty' {
        $closure_compiler_package = 'libclosure-compiler-java'
      } else {
        $closure_compiler_package = 'closure-compiler'
      }
      $static_asset_compiler_packages = [
        # Needed for minify-js
        $closure_compiler_package,
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
      $setup_closure_compiler_file = "${::zulip_scripts_path}/lib/setup-closure-compiler"
      exec{'setup_closure_compiler':
        command => "bash -c '${setup_closure_compiler_file}'",
      }
    }
    default: {
      fail('osfamily not supported')
    }
  }

  zulip::safepackage { $static_asset_compiler_packages: ensure => 'installed' }
}
