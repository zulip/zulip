#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the reverse function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("reverse").should == "function_reverse"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_reverse([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should reverse a string" do
    result = scope.function_reverse(["asdfghijkl"])
    result.should(eq('lkjihgfdsa'))
  end
end
