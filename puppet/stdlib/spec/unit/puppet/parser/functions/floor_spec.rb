#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe "the floor function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("floor").should == "function_floor"
  end

  it "should raise a ParseError if there is less than 1 argument" do
    lambda { scope.function_floor([]) }.should( raise_error(Puppet::ParseError, /Wrong number of arguments/))
  end

  it "should should raise a ParseError if input isn't numeric (eg. String)" do
    lambda { scope.function_floor(["foo"]) }.should( raise_error(Puppet::ParseError, /Wrong argument type/))
  end

  it "should should raise a ParseError if input isn't numeric (eg. Boolean)" do
    lambda { scope.function_floor([true]) }.should( raise_error(Puppet::ParseError, /Wrong argument type/))
  end

  it "should return an integer when a numeric type is passed" do
    result = scope.function_floor([12.4])
    result.is_a?(Integer).should(eq(true))
  end

  it "should return the input when an integer is passed" do
    result = scope.function_floor([7])
    result.should(eq(7))
  end

  it "should return the largest integer less than or equal to the input" do
    result = scope.function_floor([3.8])
    result.should(eq(3))
  end
end

