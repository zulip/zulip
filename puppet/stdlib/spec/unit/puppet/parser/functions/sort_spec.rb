#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the sort function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("sort").should == "function_sort"
  end

  it "should raise a ParseError if there is not 1 arguments" do
    lambda { scope.function_sort(['','']) }.should( raise_error(Puppet::ParseError))
  end

  it "should sort an array" do
    result = scope.function_sort([["a","c","b"]])
    result.should(eq(['a','b','c']))
  end

  it "should sort a string" do
    result = scope.function_sort(["acb"])
    result.should(eq('abc'))
  end
end
