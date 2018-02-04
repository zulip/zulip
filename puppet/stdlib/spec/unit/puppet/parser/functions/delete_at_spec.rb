#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the delete_at function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("delete_at").should == "function_delete_at"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_delete_at([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should delete an item at specified location from an array" do
    result = scope.function_delete_at([['a','b','c'],1])
    result.should(eq(['a','c']))
  end
end
