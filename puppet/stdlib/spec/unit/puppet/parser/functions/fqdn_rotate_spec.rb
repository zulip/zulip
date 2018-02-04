#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the fqdn_rotate function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("fqdn_rotate").should == "function_fqdn_rotate"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_fqdn_rotate([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should rotate a string and the result should be the same size" do
    scope.expects(:lookupvar).with("::fqdn").returns("127.0.0.1")
    result = scope.function_fqdn_rotate(["asdf"])
    result.size.should(eq(4))
  end

  it "should rotate a string to give the same results for one host" do
    scope.expects(:lookupvar).with("::fqdn").returns("127.0.0.1").twice
    scope.function_fqdn_rotate(["abcdefg"]).should eql(scope.function_fqdn_rotate(["abcdefg"]))
  end

  it "should rotate a string to give different values on different hosts" do
     scope.expects(:lookupvar).with("::fqdn").returns("127.0.0.1")
     val1 = scope.function_fqdn_rotate(["abcdefghijklmnopqrstuvwxyz01234567890987654321"])
     scope.expects(:lookupvar).with("::fqdn").returns("127.0.0.2")
     val2 = scope.function_fqdn_rotate(["abcdefghijklmnopqrstuvwxyz01234567890987654321"])
     val1.should_not eql(val2)
  end
end
