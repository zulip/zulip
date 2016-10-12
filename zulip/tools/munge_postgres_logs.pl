#!/usr/bin/perl
use strict;
use warnings;

while (<>) {
  # remove milliseconds
  s/(?<= \d\d:\d\d:\d\d)\.\d{3}//;
  # convert session id to process id
  s/\[[0-9a-zA-Z]+\.([0-9a-zA-Z]+)\]/"[" . hex($1) . "]"/e;
  print;
}
