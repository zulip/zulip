#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the concat function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_concat([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should be able to concat an array" do
    result = scope.function_concat([['1','2','3'],['4','5','6']])
    result.should(eq(['1','2','3','4','5','6']))
  end
end
