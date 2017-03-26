#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_float function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_float").should == "function_is_float"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_float([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if a float" do
    result = scope.function_is_float(["0.12"])
    result.should(eq(true))
  end

  it "should return false if a string" do
    result = scope.function_is_float(["asdf"])
    result.should(eq(false))
  end

  it "should return false if an integer" do
    result = scope.function_is_float(["3"])
    result.should(eq(false))
  end
  it "should return true if a float is created from an arithmetical operation" do
    result = scope.function_is_float([3.2*2])
    result.should(eq(true))
  end
end
