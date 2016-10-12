#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the size function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("size").should == "function_size"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_size([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return the size of a string" do
    result = scope.function_size(["asdf"])
    result.should(eq(4))
  end

  it "should return the size of an array" do
    result = scope.function_size([["a","b","c"]])
    result.should(eq(3))
  end
end
