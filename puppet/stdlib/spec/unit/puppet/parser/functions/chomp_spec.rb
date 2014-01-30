#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the chomp function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("chomp").should == "function_chomp"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_chomp([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should chomp the end of a string" do
    result = scope.function_chomp(["abc\n"])
    result.should(eq("abc"))
  end
end
