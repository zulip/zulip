#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_string function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_string").should == "function_is_string"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_string([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if a string" do
    result = scope.function_is_string(["asdf"])
    result.should(eq(true))
  end

  it "should return false if an integer" do
    result = scope.function_is_string(["3"])
    result.should(eq(false))
  end

  it "should return false if a float" do
    result = scope.function_is_string(["3.23"])
    result.should(eq(false))
  end

  it "should return false if an array" do
    result = scope.function_is_string([["a","b","c"]])
    result.should(eq(false))
  end
end
