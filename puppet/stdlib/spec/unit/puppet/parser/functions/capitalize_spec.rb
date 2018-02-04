#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the capitalize function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("capitalize").should == "function_capitalize"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_capitalize([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should capitalize the beginning of a string" do
    result = scope.function_capitalize(["abc"])
    result.should(eq("Abc"))
  end
end
