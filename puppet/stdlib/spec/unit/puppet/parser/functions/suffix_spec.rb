#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the suffix function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("suffix").should == "function_suffix"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_suffix([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return a suffixed array" do
    result = scope.function_suffix([['a','b','c'], 'p'])
    result.should(eq(['ap','bp','cp']))
  end
end
