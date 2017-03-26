#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the strip function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }
  it "should exist" do
    Puppet::Parser::Functions.function("strip").should == "function_strip"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_strip([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should strip a string" do
    result = scope.function_strip([" ab cd "])
    result.should(eq('ab cd'))
  end
end
