# pin.pp
# pin a release in apt, useful for unstable repositories

define apt::pin(
  $ensure          = present,
  $explanation     = "${::caller_module_name}: ${name}",
  $order           = '',
  $packages        = '*',
  $priority        = 0,
  $release         = '', # a=
  $origin          = '',
  $version         = '',
  $codename        = '', # n=
  $release_version = '', # v=
  $component       = '', # c=
  $originator      = '', # o=
  $label           = ''  # l=
) {

  include apt::params

  $preferences_d = $apt::params::preferences_d

  if $order != '' and !is_integer($order) {
    fail('Only integers are allowed in the apt::pin order param')
  }

  $pin_release_array = [
    $release,
    $codename,
    $release_version,
    $component,
    $originator,
    $label]
  $pin_release = join($pin_release_array, '')

  # Read the manpage 'apt_preferences(5)', especially the chapter
  # 'Thea Effect of APT Preferences' to understand the following logic
  # and the difference between specific and general form
  if $packages != '*' { # specific form

    if ( $pin_release != '' and ( $origin != '' or $version != '' )) or
      ( $origin != '' and ( $pin_release != '' or $version != '' )) or
      ( $version != '' and ( $pin_release != '' or $origin != '' )) {
      fail('parameters release, origin, and version are mutually exclusive')
    }

  } else { # general form

    if $version != '' {
      fail('parameter version cannot be used in general form')
    }

    if ( $pin_release != '' and $origin != '' ) or
      ( $origin != '' and $pin_release != '' ) {
      fail('parmeters release and origin are mutually exclusive')
    }

  }

  $path = $order ? {
    ''      => "${preferences_d}/${name}.pref",
    default => "${preferences_d}/${order}-${name}.pref",
  }
  file { "${name}.pref":
    ensure  => $ensure,
    path    => $path,
    owner   => root,
    group   => root,
    mode    => '0644',
    content => template('apt/pin.pref.erb'),
  }
}
