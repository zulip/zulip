#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the lstrip function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("lstrip").should == "function_lstrip"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_lstrip([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should lstrip a string" do
    result = scope.function_lstrip(["  asdf"])
    result.should(eq('asdf'))
  end
end
