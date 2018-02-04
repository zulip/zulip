#!/usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the pick function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("pick").should == "function_pick"
  end

  it 'should return the correct value' do
    scope.function_pick(['first', 'second']).should == 'first'
  end

  it 'should return the correct value if the first value is empty' do
    scope.function_pick(['', 'second']).should == 'second'
  end

  it 'should remove empty string values' do
    scope.function_pick(['', 'first']).should == 'first'
  end

  it 'should remove :undef values' do
    scope.function_pick([:undef, 'first']).should == 'first'
  end

  it 'should remove :undefined values' do
    scope.function_pick([:undefined, 'first']).should == 'first'
  end

  it 'should error if no values are passed' do
    expect { scope.function_pick([]) }.to raise_error(Puppet::Error, /Must provide non empty value./)
  end
end
