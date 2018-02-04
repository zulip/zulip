#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_mac_address function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_mac_address").should == "function_is_mac_address"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_mac_address([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if a valid mac address" do
    result = scope.function_is_mac_address(["00:a0:1f:12:7f:a0"])
    result.should(eq(true))
  end

  it "should return false if octets are out of range" do
    result = scope.function_is_mac_address(["00:a0:1f:12:7f:g0"])
    result.should(eq(false))
  end

  it "should return false if not valid" do
    result = scope.function_is_mac_address(["not valid"])
    result.should(eq(false))
  end
end
