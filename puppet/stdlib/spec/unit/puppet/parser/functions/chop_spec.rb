#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the chop function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("chop").should == "function_chop"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_chop([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should chop the end of a string" do
    result = scope.function_chop(["asdf\n"])
    result.should(eq("asdf"))
  end
end
