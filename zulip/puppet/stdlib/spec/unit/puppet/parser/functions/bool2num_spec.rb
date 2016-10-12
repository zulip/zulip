#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the bool2num function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("bool2num").should == "function_bool2num"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_bool2num([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should convert true to 1" do
    result = scope.function_bool2num([true])
    result.should(eq(1))
  end

  it "should convert false to 0" do
    result = scope.function_bool2num([false])
    result.should(eq(0))
  end
end
