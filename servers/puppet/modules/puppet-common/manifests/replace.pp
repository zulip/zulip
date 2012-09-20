# common/manifests/defines/replace.pp -- replace a pattern in a file with a string
# Copyright (C) 2007 David Schmitt <david@schmitt.edv-bus.at>
# See LICENSE for the full license granted to you.

# Usage:
#
# replace { description: 
#           file => "filename",
#           pattern => "regexp",
#           replacement => "replacement"
#
# Example:
# To replace the current port in /etc/munin/munin-node.conf
# with a new port, but only disturbing the file when needed:
#
# replace { set_munin_node_port:
# 	file => "/etc/munin/munin-node.conf",
# 	pattern => "^port (?!$port)[0-9]*",
# 	replacement => "port $port"
# }  

define common::replace($file, $pattern, $replacement) {
	$pattern_no_slashes = slash_escape($pattern)
	$replacement_no_slashes = slash_escape($replacement)
	exec { "replace_${pattern}_${file}":
		command => "/usr/bin/perl -pi -e 's/${pattern_no_slashes}/${replacement_no_slashes}/' '${file}'",
		onlyif => "/usr/bin/perl -ne 'BEGIN { \$ret = 1; } \$ret = 0 if /${pattern_no_slashes}/ && ! /\\Q${replacement_no_slashes}\\E/; END { exit \$ret; }' '${file}'",
		alias => "exec_$name",
	}
}
