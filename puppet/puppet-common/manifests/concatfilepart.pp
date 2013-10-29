# Inspired by David Schmitt's concatenated_file.pp

define common::concatfilepart (
  $ensure = present,
  $file,
  $content = false,
  $source  = false,
  $manage  = false
) {

  # Resulting file
  if defined(File[$file]) {
    debug("${file} already defined")
  } else {
    file {$file:
      ensure => present,
    }
  }

  # Directory containing file parts
  $dir = "${file}.d"

  if defined(File[$dir]) {
    debug("${dir} already defined")
  } else {
    file {$dir:
      ensure  => directory,
      mode    => 0600,
      source  => "puppet:///modules/common/empty/",
      recurse => $manage,
      purge   => $manage,
      force   => $manage,
      ignore  => '.ignore',
    }
  }

  if $notify {
    if $content {
      file {"${dir}/${name}":
        ensure  => $ensure,
        content => $content,
        mode    => 0600,
        notify  => [Exec["${file} concatenation"], $notify],
      }
    } else {
      file {"${dir}/${name}":
        ensure  => $ensure,
        source  => $source,
        mode    => 0600,
        notify  => [Exec["${file} concatenation"], $notify],
      }
    }
  } else {
    if $content {
      file {"${dir}/${name}":
        ensure  => $ensure,
        content => $content,
        mode    => 0600,
        notify  => Exec["${file} concatenation"],
      }
    } else {
      file {"${dir}/${name}":
        ensure  => $ensure,
        source  => $source,
        mode    => 0600,
        notify  => Exec["${file} concatenation"],
      }
    }
  }

  # The actual file generation
  if defined(Exec["${file} concatenation"]) {

    debug("Blah")
    #Exec["${file} concatenation"] {
    # require +> File["${dir}/${name}"],
    #}

  } else {
    # use >| to force clobbering the target file
    exec { "${file} concatenation":
      command => "/usr/bin/find ${dir} -maxdepth 1 -type f ! -name '*puppettmp' -print0 | sort -z | xargs -0 cat >| ${file}",
      refreshonly => true,
      subscribe => File[$dir],
      before => File[$file],
    #  require => File["${dir}/${name}"],
      #alias => [ "concat_${name}", "concat_${dir}"] ,
    }
  }

}
