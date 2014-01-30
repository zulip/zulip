#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the type function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }
  it "should exist" do
    Puppet::Parser::Functions.function("type").should == "function_type"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_type([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return string when given a string" do
    result = scope.function_type(["aaabbbbcccc"])
    result.should(eq('string'))
  end

  it "should return array when given an array" do
    result = scope.function_type([["aaabbbbcccc","asdf"]])
    result.should(eq('array'))
  end

  it "should return hash when given a hash" do
    result = scope.function_type([{"a"=>1,"b"=>2}])
    result.should(eq('hash'))
  end

  it "should return integer when given an integer" do
    result = scope.function_type(["1"])
    result.should(eq('integer'))
  end

  it "should return float when given a float" do
    result = scope.function_type(["1.34"])
    result.should(eq('float'))
  end

  it "should return boolean when given a boolean" do
    result = scope.function_type([true])
    result.should(eq('boolean'))
  end
end
