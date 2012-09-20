import "../manifests/concatfilepart.pp"

common::concatfilepart{"0_blah":
  ensure  => absent,
  content => "Z",
  file    => "/tmp/test-concat.txt",
}

common::concatfilepart{"1_body":
  ensure => absent,
  content => "B",
  file    => "/tmp/test-concat.txt",
}

common::concatfilepart{"9_footer":
  ensure  => absent,
  content => "C",
  file    => "/tmp/test-concat.txt",
}
