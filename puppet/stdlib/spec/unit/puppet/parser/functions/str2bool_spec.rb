#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the str2bool function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("str2bool").should == "function_str2bool"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_str2bool([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should convert string 'true' to true" do
    result = scope.function_str2bool(["true"])
    result.should(eq(true))
  end

  it "should convert string 'undef' to false" do
    result = scope.function_str2bool(["undef"])
    result.should(eq(false))
  end
  
  it "should return the boolean it was called with" do
    result = scope.function_str2bool([true])
    result.should(eq(true))
    result = scope.function_str2bool([false])
    result.should(eq(false))
  end
end
