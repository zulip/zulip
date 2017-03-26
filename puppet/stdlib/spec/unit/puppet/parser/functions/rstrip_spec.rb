#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the rstrip function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("rstrip").should == "function_rstrip"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_rstrip([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should rstrip a string" do
    result = scope.function_rstrip(["asdf  "])
    result.should(eq('asdf'))
  end

  it "should rstrip each element in an array" do
    result = scope.function_rstrip([["a ","b ", "c "]])
    result.should(eq(['a','b','c']))
  end
end
