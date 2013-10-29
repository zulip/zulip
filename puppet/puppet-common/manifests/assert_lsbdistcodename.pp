# common/manifests/classes/lsb_release.pp -- request the installation of
# lsb_release to get to lsbdistcodename, which is used throughout the manifests
#
# Copyright (C) 2007 David Schmitt <david@schmitt.edv-bus.at>
# See LICENSE for the full license granted to you.

# Changelog:
# 2007-08-26: micah <micah@riseup.net> reported, that lsb_release can report
#	nonsensical values for lsbdistcodename; assert_lsbdistcodename now
#	recognises "n/a" and acts accordingly

# This lightweight class only asserts that $lsbdistcodename is set.
# If the assertion fails, an error is printed on the server
# 
# To fail individual resources on a missing lsbdistcodename, require
# Exec[assert_lsbdistcodename] on the specific resource
class common::assert_lsbdistcodename {

	case $lsbdistcodename {
		'': {
			err("Please install lsb_release or set facter_lsbdistcodename in the environment of $fqdn")
			exec { "false # assert_lsbdistcodename": alias => assert_lsbdistcodename }
		}
		'n/a': {
			case $operatingsystem {
				"Debian": {
					err("lsb_release was unable to report your distcodename; This seems to indicate a broken apt/sources.list on $fqdn")
				}
				default: {
					err("lsb_release was unable to report your distcodename; please set facter_lsbdistcodename in the environment of $fqdn")
				}
			}
			exec { "false # assert_lsbdistcodename": alias => assert_lsbdistcodename }
		}
		default: {
			exec { "true # assert_lsbdistcodename": alias => assert_lsbdistcodename }
			exec { "true # require_lsbdistcodename": alias => require_lsbdistcodename }
		}
	}

}
