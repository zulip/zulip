#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the squeeze function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("squeeze").should == "function_squeeze"
  end

  it "should raise a ParseError if there is less than 2 arguments" do
    lambda { scope.function_squeeze([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should squeeze a string" do
    result = scope.function_squeeze(["aaabbbbcccc"])
    result.should(eq('abc'))
  end

  it "should squeeze all elements in an array" do
    result = scope.function_squeeze([["aaabbbbcccc","dddfff"]])
    result.should(eq(['abc','df']))
  end
end
