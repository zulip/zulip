#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the any2array function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("any2array").should == "function_any2array"
  end

  it "should return an empty array if there is less than 1 argument" do
    result = scope.function_any2array([])
    result.should(eq([]))
  end

  it "should convert boolean true to [ true ] " do
    result = scope.function_any2array([true])
    result.should(eq([true]))
  end

  it "should convert one object to [object]" do
    result = scope.function_any2array(['one'])
    result.should(eq(['one']))
  end

  it "should convert multiple objects to [objects]" do
    result = scope.function_any2array(['one', 'two'])
    result.should(eq(['one', 'two']))
  end

  it "should return empty array it was called with" do
    result = scope.function_any2array([[]])
    result.should(eq([]))
  end

  it "should return one-member array it was called with" do
    result = scope.function_any2array([['string']])
    result.should(eq(['string']))
  end

  it "should return multi-member array it was called with" do
    result = scope.function_any2array([['one', 'two']])
    result.should(eq(['one', 'two']))
  end

  it "should return members of a hash it was called with" do
    result = scope.function_any2array([{ 'key' => 'value' }])
    result.should(eq(['key', 'value']))
  end

  it "should return an empty array if it was called with an empty hash" do
    result = scope.function_any2array([{ }])
    result.should(eq([]))
  end
end
