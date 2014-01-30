#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the join function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("join").should == "function_join"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_join([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should join an array into a string" do
    result = scope.function_join([["a","b","c"], ":"])
    result.should(eq("a:b:c"))
  end
end
