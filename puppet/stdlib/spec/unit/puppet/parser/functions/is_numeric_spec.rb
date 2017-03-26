#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_numeric function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_numeric").should == "function_is_numeric"
  end

  it "should raise a ParseError if there is less than 1 argument" do
    lambda { scope.function_is_numeric([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if an integer" do
    result = scope.function_is_numeric(["3"])
    result.should(eq(true))
  end

  it "should return true if a float" do
    result = scope.function_is_numeric(["3.2"])
    result.should(eq(true))
  end

  it "should return true if an integer is created from an arithmetical operation" do
    result = scope.function_is_numeric([3*2])
    result.should(eq(true))
  end

  it "should return true if a float is created from an arithmetical operation" do
    result = scope.function_is_numeric([3.2*2])
    result.should(eq(true))
  end

  it "should return false if a string" do
    result = scope.function_is_numeric(["asdf"])
    result.should(eq(false))
  end
end
