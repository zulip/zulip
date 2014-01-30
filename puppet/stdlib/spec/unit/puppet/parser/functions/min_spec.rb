#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe "the min function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("min").should == "function_min"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_min([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should be able to compare strings" do
    scope.function_min(["albatross","dog","horse"]).should(eq("albatross"))
  end

  it "should be able to compare numbers" do
    scope.function_min([6,8,4]).should(eq(4))
  end

  it "should be able to compare a number with a stringified number" do
    scope.function_min([1,"2"]).should(eq(1))
  end
end
