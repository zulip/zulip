#!/usr/bin/env perl


# Nagios plugin that sends Nagios events to PagerDuty.
#
# Copyright (c) 2011, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of PagerDuty Inc nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL PAGERDUTY INC BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


use Pod::Usage;
use Getopt::Long;
use Sys::Syslog;
use HTTP::Request::Common qw(POST);
use HTTP::Status qw(is_client_error);
use LWP::UserAgent;
use File::Path;
use Fcntl qw(:flock);


=head1 NAME

pagerduty_nagios -- Send Nagios events to the PagerDuty alert system

=head1 SYNOPSIS

pagerduty_nagios enqueue [options]

pagerduty_nagios flush [options]

=head1 DESCRIPTION

  This script passes events from Nagios to the PagerDuty alert system. It's
  meant to be run as a Nagios notification plugin. For more details, please see
  the PagerDuty Nagios integration docs at:
  http://www.pagerduty.com/docs/nagios-integration.

  When called in the "enqueue" mode, the script loads a Nagios notification out
  of the environment and into the event queue.  It then tries to flush the
  queue by sending any enqueued events to the PagerDuty server.  The script is
  typically invoked in this mode from a Nagios notification handler.

  When called in the "flush" mode, the script simply tries to send any enqueued
  events to the PagerDuty server.  This mode is typically invoked by cron.  The
  purpose of this mode is to retry any events that couldn't be sent to the
  PagerDuty server for whatever reason when they were initially enqueued.

=head1 OPTIONS

  --api-base URL
    The base URL used to communicate with PagerDuty.  The default option here
    should be fine, but adjusting it may make sense if your firewall doesn't
    pass HTTPS traffic for some reason.  See the PagerDuty Nagios integration
    docs for details.

  --field KEY=VALUE
    Add this key-value pair to the event being passed to PagerDuty.  The script
    automatically gathers Nagios macros out of the environment, so there's no
    need to specify these explicitly.  This option can be repeated as many
    times as necessary to pass multiple key-value pairs.  This option is only
    useful when an event is being enqueued.0

  --help
    Display documentation for the script.

  --queue-dir DIR
    Path to the directory to use to store the event queue.  By default, we use
    /tmp/pagerduty_nagios.

  --verbose
    Turn on extra debugging information.  Useful for debugging.

=cut

# This release tested on:
# Debian Sarge (Perl 5.8.4)
# Ubuntu 9.04  (Perl 5.10.0)

my $opt_api_base = "https://events.pagerduty.com/nagios/2010-04-15";
my %opt_fields;
my $opt_help;
my $opt_queue_dir = "/tmp/pagerduty_nagios";
my $opt_verbose;


sub get_queue_from_dir {
	my $dh;
	
	unless (opendir($dh, $opt_queue_dir)) {
		syslog(LOG_ERR, "opendir %s failed: %s", $opt_queue_dir, $!);
		die $!;
	}
	
	my @files;
	while (my $f = readdir($dh)) {
		next unless $f =~ /^pd_(\d+)_\d+\.txt$/;
		push @files, [int($1), $f];
	}

	closedir($dh);
	
	@files = sort { @{$a}[0] <=> @{$b}[0] } @files;
	return map { @{$_}[1] } @files;
}


sub flush_queue {
	my @files = get_queue_from_dir();
	my $ua = LWP::UserAgent->new;

	# It's not a big deal if we don't get the message through the first time.
	# It will get sent the next time cron fires.
	$ua->timeout(15);
	
	foreach (@files) {
		my $filename = "$opt_queue_dir/$_";
		my $fd;
		my %event;

		print STDERR "==== Now processing: $filename\n" if $opt_verbose;
		
		unless (open($fd, "<", $filename)) {
			syslog(LOG_ERR, "open %s for read failed: %s", $filename, $!);
			die $!;
		}
		
		while (<$fd>) {
			chomp;
			my @fields = split("=", $_, 2);
			$event{$fields[0]} = $fields[1];
		}
		
		close($fd);

		my $req = POST("$opt_api_base/create_event", \%event);
		
		if ($opt_verbose) {
			my $s = $req->as_string;
			print STDERR "Request:\n$s\n";
		}
		
		my $resp = $ua->request($req);
		
		if ($opt_verbose) {
			my $s = $resp->as_string;
			print STDERR "Response:\n$s\n";
		}

		if ($resp->is_success) {
			syslog(LOG_INFO, "Nagios event in file %s ACCEPTED by the PagerDuty server.", $filename);
			unlink($filename);
		}
		elsif (is_client_error($resp->code)) {
			syslog(LOG_WARNING, "Nagios event in file %s REJECTED by the PagerDuty server.  Server says: %s", $filename, $resp->content);
			unlink($filename);
		}
		else {
			# Something else went wrong.
			syslog(LOG_WARNING, "Nagios event in file %s DEFERRED due to network/server problems.", $filename);
			return 0;
		}
	}

	# Everything that needed to be sent was sent.
	return 1;
}


sub lock_and_flush_queue {
	# Serialize access to the queue directory while we flush.
	# (We don't want more than one flush at once.)
	
	my $lock_filename = "$opt_queue_dir/lockfile";
	my $lock_fd;
	
	unless (open($lock_fd, ">", $lock_filename)) {
		syslog(LOG_ERR, "open %s for write failed: %s", $lock_filename, $!);
		die $!;
	}

	unless (flock($lock_fd, LOCK_EX)) {
		syslog(LOG_ERR, "flock %s failed: %s", $lock_filename, $!);
		die $!;
	}
	
	my $ret = flush_queue();
	
	close($lock_fd);
	
	return $ret;
}


sub enqueue_event {
	my %event;

	# Scoop all the Nagios related stuff out of the environment.
	while ((my $k, my $v) = each %ENV) {
		next unless $k =~ /^NAGIOS_(.*)$/;
		$event{$1} = $v;
	}

	# Apply any other variables that were passed in.
	%event = (%event, %opt_fields);

	$event{"pd_version"} = "1.0";
	
	# Right off the bat, enqueue the event.  Nothing tiem consuming should come
	# before here (i.e. no locks or remote connections), because we want to
	# make sure we get the event written out within the Nagios notification
	# timeout.  If we get killed off after that, it isn't a big deal.
	
	my $filename = sprintf("$opt_queue_dir/pd_%u_%u.txt", time(), $$);
	my $fd;
	
	unless (open($fd, ">", $filename)) {
		syslog(LOG_ERR, "open %s for write failed: %s", $filename, $!);
		die $!;
	}
	
	while ((my $k, my $v) = each %event) {
		# "=" can't occur in the keyname, and "\n" can't occur anywhere.
		# (Nagios follows this already, so I think we're safe)
		print $fd "$k=$v\n";
	}
	
	close($fd);
}

###########

GetOptions("api-base=s" => \$opt_api_base,
		   "field=s%" => \%opt_fields,
		   "help" => \$opt_help,
		   "queue-dir=s" => \$opt_queue_dir,
		   "verbose" => \$opt_verbose
		  ) || pod2usage(2);

pod2usage(2) if @ARGV < 1 ||
	 (($ARGV[0] ne "enqueue") && ($ARGV[0] ne "flush"));
	 
pod2usage(-verbose => 3) if $opt_help;

my @log_mode = ("nofatal", "pid");
push(@log_mode, "perror") if $opt_verbose;

openlog("pagerduty_nagios", join(",", @log_mode), LOG_LOCAL0);

# This function automatically terminates the program on things like permission
# errors.
mkpath($opt_queue_dir);

if ($ARGV[0] eq "enqueue") {
	enqueue_event();
	lock_and_flush_queue();
}
elsif ($ARGV[0] eq "flush") {
	lock_and_flush_queue();
}
