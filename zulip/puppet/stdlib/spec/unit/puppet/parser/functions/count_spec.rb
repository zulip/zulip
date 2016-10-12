#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe "the count function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("count").should == "function_count"
  end

  it "should raise a ArgumentError if there is more than 2 arguments" do
    lambda { scope.function_count(['foo', 'bar', 'baz']) }.should( raise_error(ArgumentError))
  end

  it "should be able to count arrays" do
    scope.function_count([["1","2","3"]]).should(eq(3))
  end

  it "should be able to count matching elements in arrays" do
    scope.function_count([["1", "2", "2"], "2"]).should(eq(2))
  end

  it "should not count nil or empty strings" do
    scope.function_count([["foo","bar",nil,""]]).should(eq(2))
  end

  it 'does not count an undefined hash key or an out of bound array index (which are both :undef)' do
    expect(scope.function_count([["foo",:undef,:undef]])).to eq(1)
  end
end
