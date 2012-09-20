import "../manifests/concatfilepart.pp"

common::concatfilepart{"0_header":
  ensure  => absent,
  content => "A",
  file    => "/tmp/test-concat.txt",
}

common::concatfilepart{"1_body":
  ensure => present,
  content => "B",
  file    => "/tmp/test-concat.txt",
}

common::concatfilepart{"9_footer":
  ensure  => present,
  content => "C",
  file    => "/tmp/test-concat.txt",
}
