#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_ip_address function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_ip_address").should == "function_is_ip_address"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_ip_address([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if an IPv4 address" do
    result = scope.function_is_ip_address(["1.2.3.4"])
    result.should(eq(true))
  end

  it "should return true if a full IPv6 address" do
    result = scope.function_is_ip_address(["fe80:0000:cd12:d123:e2f8:47ff:fe09:dd74"])
    result.should(eq(true))
  end

  it "should return true if a compressed IPv6 address" do
    result = scope.function_is_ip_address(["fe00::1"])
    result.should(eq(true))
  end

  it "should return false if not valid" do
    result = scope.function_is_ip_address(["asdf"])
    result.should(eq(false))
  end

  it "should return false if IP octets out of range" do
    result = scope.function_is_ip_address(["1.1.1.300"])
    result.should(eq(false))
  end
end
