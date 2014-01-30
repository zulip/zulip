#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the zip function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_zip([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should be able to zip an array" do
    result = scope.function_zip([['1','2','3'],['4','5','6']])
    result.should(eq([["1", "4"], ["2", "5"], ["3", "6"]]))
  end
end
