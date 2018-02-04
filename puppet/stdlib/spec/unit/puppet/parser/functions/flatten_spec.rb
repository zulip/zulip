#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the flatten function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }
  it "should exist" do
    Puppet::Parser::Functions.function("flatten").should == "function_flatten"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_flatten([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should raise a ParseError if there is more than 1 argument" do
    lambda { scope.function_flatten([[], []]) }.should( raise_error(Puppet::ParseError))
  end

  it "should flatten a complex data structure" do
    result = scope.function_flatten([["a","b",["c",["d","e"],"f","g"]]])
    result.should(eq(["a","b","c","d","e","f","g"]))
  end

  it "should do nothing to a structure that is already flat" do
    result = scope.function_flatten([["a","b","c","d"]])
    result.should(eq(["a","b","c","d"]))
  end
end
