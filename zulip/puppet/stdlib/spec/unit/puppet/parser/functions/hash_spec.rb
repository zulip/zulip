#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the hash function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("hash").should == "function_hash"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_hash([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should convert an array to a hash" do
    result = scope.function_hash([['a',1,'b',2,'c',3]])
    result.should(eq({'a'=>1,'b'=>2,'c'=>3}))
  end
end
