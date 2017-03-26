#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the time function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("time").should == "function_time"
  end

  it "should raise a ParseError if there is more than 2 arguments" do
    lambda { scope.function_time(['','']) }.should( raise_error(Puppet::ParseError))
  end

  it "should return a number" do
    result = scope.function_time([])
    result.should be_an(Integer)
  end

  it "should be higher then when I wrote this test" do
    result = scope.function_time([])
    result.should(be > 1311953157)
  end

  it "should be lower then 1.5 trillion" do
    result = scope.function_time([])
    result.should(be < 1500000000)
  end
end
