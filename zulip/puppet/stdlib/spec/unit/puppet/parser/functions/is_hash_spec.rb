#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_hash function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_hash").should == "function_is_hash"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_hash([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if passed a hash" do
    result = scope.function_is_hash([{"a"=>1,"b"=>2}])
    result.should(eq(true))
  end

  it "should return false if passed an array" do
    result = scope.function_is_hash([["a","b"]])
    result.should(eq(false))
  end

  it "should return false if passed a string" do
    result = scope.function_is_hash(["asdf"])
    result.should(eq(false))
  end
end
