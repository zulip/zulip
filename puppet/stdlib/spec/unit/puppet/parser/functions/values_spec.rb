#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the values function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("values").should == "function_values"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_values([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return values from a hash" do
    result = scope.function_values([{'a'=>'1','b'=>'2','c'=>'3'}])
    # =~ is the RSpec::Matchers::MatchArray matcher.
    # A.K.A. "array with same elements" (multiset) matching
    result.should =~ %w{ 1 2 3 }
  end

  it "should return a multiset" do
    result = scope.function_values([{'a'=>'1','b'=>'3','c'=>'3'}])
    result.should     =~ %w{ 1 3 3 }
    result.should_not =~ %w{ 1 3 }
  end

  it "should raise a ParseError unless a Hash is provided" do
    lambda { scope.function_values([['a','b','c']]) }.should( raise_error(Puppet::ParseError))
  end
end
