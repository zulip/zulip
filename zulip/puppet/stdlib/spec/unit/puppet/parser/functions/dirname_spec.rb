#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the dirname function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("dirname").should == "function_dirname"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_dirname([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return dirname for an absolute path" do
    result = scope.function_dirname(['/path/to/a/file.ext'])
    result.should(eq('/path/to/a'))
  end

  it "should return dirname for a relative path" do
    result = scope.function_dirname(['path/to/a/file.ext'])
    result.should(eq('path/to/a'))
  end
end
