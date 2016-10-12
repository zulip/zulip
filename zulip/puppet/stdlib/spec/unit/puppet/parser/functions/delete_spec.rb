#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the delete function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("delete").should == "function_delete"
  end

  it "should raise a ParseError if there are fewer than 2 arguments" do
    lambda { scope.function_delete([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should raise a ParseError if there are greater than 2 arguments" do
    lambda { scope.function_delete([[], 'foo', 'bar']) }.should( raise_error(Puppet::ParseError))
  end

  it "should raise a TypeError if a number is passed as the first argument" do
    lambda { scope.function_delete([1, 'bar']) }.should( raise_error(TypeError))
  end

  it "should delete all instances of an element from an array" do
    result = scope.function_delete([['a','b','c','b'],'b'])
    result.should(eq(['a','c']))
  end

  it "should delete all instances of a substring from a string" do
    result = scope.function_delete(['foobarbabarz','bar'])
    result.should(eq('foobaz'))
  end

  it "should delete a key from a hash" do
    result = scope.function_delete([{ 'a' => 1, 'b' => 2, 'c' => 3 },'b'])
    result.should(eq({ 'a' => 1, 'c' => 3 }))
  end

end
