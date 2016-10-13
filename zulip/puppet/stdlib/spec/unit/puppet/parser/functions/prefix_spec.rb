#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the prefix function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("prefix").should == "function_prefix"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_prefix([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return a prefixed array" do
    result = scope.function_prefix([['a','b','c'], 'p'])
    result.should(eq(['pa','pb','pc']))
  end
end
