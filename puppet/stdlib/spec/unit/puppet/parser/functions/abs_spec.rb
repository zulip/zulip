#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe "the abs function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("abs").should == "function_abs"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_abs([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should convert a negative number into a positive" do
    result = scope.function_abs(["-34"])
    result.should(eq(34))
  end

  it "should do nothing with a positive number" do
    result = scope.function_abs(["5678"])
    result.should(eq(5678))
  end
end
