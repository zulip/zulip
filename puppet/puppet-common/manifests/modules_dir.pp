# common/manifests/defines/modules_dir.pp -- create a default directory
# for storing module specific information
#
# Copyright (C) 2007 David Schmitt <david@schmitt.edv-bus.at>
# See LICENSE for the full license granted to you.

# Usage:
# modules_dir { ["common", "common/dir1", "common/dir2" ]: }
define modules_dir (
		$mode = 0644, $owner = root, $group = 0
	)
{
	$dir = "/var/lib/puppet/modules/${name}"
	if defined(File[$dir]) {
		debug("${dir} already defined")
	} else {
		file {
			"/var/lib/puppet/modules/${name}":
				source => [ "puppet:///modules/${name}/modules_dir", "puppet:///modules/common/empty"],
				checksum => mtime,
				# ignore the placeholder
				ignore => '\.ignore', 
				recurse => true, purge => true, force => true,
				mode => $mode, owner => $owner, group => $group;
		}
	}
}
