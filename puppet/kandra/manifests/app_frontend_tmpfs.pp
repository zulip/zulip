class kandra::app_frontend_tmpfs {
  $disk = '/dev/nvme1n1'
  $partition = "${disk}p1"

  exec { 'create partition table':
    command => "/usr/sbin/parted -s ${disk} mklabel gpt",
    unless  => "/usr/sbin/blkid -s PTUUID ${disk}",
  }

  exec { 'create partition':
    command => "/usr/sbin/parted -a optimal -s ${disk} mkpart slack-tmp ext4 0% 100%",
    unless  => "/usr/sbin/blkid ${partition}",
    require => Exec['create partition table'],
  }

  exec { 'format partition':
    command => "/sbin/mkfs.ext4 -L slack-tmp ${partition}",
    unless  => "/sbin/blkid -t TYPE=ext4 ${partition}",
    require => Exec['create partition'],
  }

  file { '/tmp/slack-conversions':
    ensure => 'directory',
    mode   => '0755',
    owner  => 'root',
    group  => 'root',
  }
  mount { '/tmp/slack-conversions':
    ensure  => 'mounted',
    device  => $partition,
    fstype  => 'ext4',
    atboot  => true,
    options => 'defaults,noatime,discard,commit=60,errors=remount-ro',
    require => Exec['format partition'],
  }
}
