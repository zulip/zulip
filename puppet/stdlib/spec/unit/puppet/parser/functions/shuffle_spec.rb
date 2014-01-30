#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the shuffle function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("shuffle").should == "function_shuffle"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_shuffle([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should shuffle a string and the result should be the same size" do
    result = scope.function_shuffle(["asdf"])
    result.size.should(eq(4))
  end

  it "should shuffle a string but the sorted contents should still be the same" do
    result = scope.function_shuffle(["adfs"])
    result.split("").sort.join("").should(eq("adfs"))
  end
end
