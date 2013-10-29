# common/manifests/defines/modules_file.pp -- use a modules_dir to store module
# specific files
#
# Copyright (C) 2007 David Schmitt <david@schmitt.edv-bus.at>
# See LICENSE for the full license granted to you.

# Usage:
# modules_file { "module/file":
# 		source => "puppet://..",
# 		mode   => 644,   # default
# 		owner  => root,  # default
#		group  => root,  # default
# }
define common::modules_file (
		$source,
		$mode = 0644, $owner = root, $group = root
	)
{
	file {
		"/var/lib/puppet/modules/${name}":
			source => $source,
			mode => $mode, owner => $owner, group => $group;
	}
}
