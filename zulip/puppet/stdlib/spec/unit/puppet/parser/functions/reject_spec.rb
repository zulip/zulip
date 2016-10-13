#!/usr/bin/env ruby

require 'spec_helper'

describe "the reject function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("reject").should == "function_reject"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_reject([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should reject contents from an array" do
    result = scope.function_reject([["1111", "aaabbb","bbbccc","dddeee"], "bbb"])
    result.should(eq(["1111", "dddeee"]))
  end
end
