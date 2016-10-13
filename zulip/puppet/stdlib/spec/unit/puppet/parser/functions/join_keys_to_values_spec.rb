#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the join_keys_to_values function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("join_keys_to_values").should == "function_join_keys_to_values"
  end

  it "should raise a ParseError if there are fewer than two arguments" do
    lambda { scope.function_join_keys_to_values([{}]) }.should raise_error Puppet::ParseError
  end

  it "should raise a ParseError if there are greater than two arguments" do
    lambda { scope.function_join_keys_to_values([{}, 'foo', 'bar']) }.should raise_error Puppet::ParseError
  end

  it "should raise a TypeError if the first argument is an array" do
    lambda { scope.function_join_keys_to_values([[1,2], ',']) }.should raise_error TypeError
  end

  it "should raise a TypeError if the second argument is an array" do
    lambda { scope.function_join_keys_to_values([{}, [1,2]]) }.should raise_error TypeError
  end

  it "should raise a TypeError if the second argument is a number" do
    lambda { scope.function_join_keys_to_values([{}, 1]) }.should raise_error TypeError
  end

  it "should return an empty array given an empty hash" do
    result = scope.function_join_keys_to_values([{}, ":"])
    result.should == []
  end

  it "should join hash's keys to its values" do
    result = scope.function_join_keys_to_values([{'a'=>1,2=>'foo',:b=>nil}, ":"])
    result.should =~ ['a:1','2:foo','b:']
  end
end
