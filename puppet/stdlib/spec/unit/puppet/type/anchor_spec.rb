#!/usr/bin/env ruby

require 'puppet'

anchor = Puppet::Type.type(:anchor).new(:name => "ntp::begin")

describe anchor do
  it "should stringify normally" do
    anchor.to_s.should == "Anchor[ntp::begin]"
  end
end
