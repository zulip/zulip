
## START LIBRARY FUNCTIONS

# Usage: Variant on common:append_if_no_such_line that initializes the
# File object for you.
define common::append ($file, $line) {
  file { $file:
    ensure => file,
  }
  exec { "/bin/echo '$line' >> '$file'":
    unless => "/bin/grep -Fxqe '$line' '$file'",
    path => "/bin",
    subscribe => File[$file],
  }
}
