#!/usr/bin/perl -w
#
# check_debian_packages - nagios plugin
#
#
# Copyright (C) 2005 Francesc Guasch
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# Report bugs to: frankie@etsetb.upc.edu
#
use strict;
use lib '/usr/lib/nagios/plugins';
use utils qw(%ERRORS &print_revision &support &usage);
use Getopt::Long;

my $VERSION = '0.06';

my $RET = 'OK';
my $LOCK_FILE = "/var/lib/dpkg/lock";
my $CMD_APT = "/usr/bin/apt-get -s upgrade";
my $TIMEOUT = 60;
my $DEBUG	= 0;

#####################################################################
#
# Command line arguments
#

sub print_usage ();

my ($help,$version);
GetOptions(    help => \$help,
			  debug => \$DEBUG,
		    version => \$version,
		'timeout=s' => \$TIMEOUT
);
my ($PROGNAME) = $0 =~ m#.*/(.*)#;

if ($help) {
	print_revision($PROGNAME,"\$Revision: $VERSION \$");
	print "Copyright (c) 2005 Francesc Guasch - Ortiz

	Perl Check debian packages plugin for Nagios

";
	print_usage();
	exit($ERRORS{OK});
}

if ($version) {
	print_revision($PROGNAME,"\$Revision: $VERSION \$");
	exit($ERRORS{OK});
}

#
# unlikely but compliant
#
$SIG{'ALRM'} = sub {
	print ("ERROR: Timeout\n");
	exit $ERRORS{"UNKNOWN"};
};
alarm($TIMEOUT);


######################################################################
#
# subs
#

sub print_usage () {
	print "Usage: $PROGNAME [--debug] [--version] [--help]"
			." [--timeout=$TIMEOUT]\n";
}

sub add_info {
	my ($info,$type,$pkg) = @_;
	$$info .= scalar(keys %$pkg)." new pkgs in $type: ";
	if (keys %$pkg< 5 ) {
		$$info .= join " ",keys %$pkg;
	} else {
		my $alguns = join " ",keys %$pkg;
		$alguns = substr($alguns,0,80);
		$alguns .= "...";
		$$info .= $alguns;
	}
}

sub exit_unknown {
	my ($info) = @_;
	chomp $info;
    $RET='UNKNOWN';
    print "$RET: $info\n";
    exit $ERRORS{$RET};
};

sub run_apt {
	my ($pkg,$ver,$type,$release);
	open APT,"$CMD_APT 2>&1|" or exit_unknown($!);
	my (%stable,%security,%other);
	while (<APT>) {
		print "APT: $_" if $DEBUG;
		exit_unknown($_) if /(Could not open lock file)|(Could not get lock)/;
		next unless /^Inst/;
		($pkg,$ver,$release) = /Inst (.*?) .*\((.*?) (.*?)\)/;
		print "$_\npkg=$pkg ver=$ver release=$release\n" if $DEBUG;
		die "$_\n" unless defined $release;
		$release = 'stable'  
				if $release =~ /stable$/ && $release !~/security/i;
		$release = 'security' 
				if $release =~ /security/i;
		if ($release eq 'stable') {
			$stable{$pkg} = $ver;
		} elsif ($release eq 'security') {
			$security{$pkg} = $ver;
		} else {
			$other{$pkg}=$ver;
		}
	}
	close APT;
	my $info = '';
	if (keys (%security)) {
		$RET = 'CRITICAL';
		add_info(\$info,'security',\%security);
	} elsif (keys (%other) or keys(%stable)) {
    	$RET = 'WARNING';
		add_info(\$info,'stable',\%stable);
		add_info(\$info,'other',\%other) if keys %other;
	}
	print "$RET: $info\n";
}

run_apt();
exit $ERRORS{$RET};
