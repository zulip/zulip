#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe "the validate_slength function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("validate_slength").should == "function_validate_slength"
  end

  it "should raise a ParseError if there is less than 2 arguments" do
    expect { scope.function_validate_slength([]) }.to(raise_error(Puppet::ParseError))
    expect { scope.function_validate_slength(["asdf"]) }.to(raise_error(Puppet::ParseError))
  end

  it "should raise a ParseError if argument 2 doesn't convert to a fixnum" do
    expect { scope.function_validate_slength(["moo",["2"]]) }.to(raise_error(Puppet::ParseError, /Couldn't convert whatever you passed/))
  end

  it "should raise a ParseError if argument 2 converted, but to 0, e.g. a string" do
    expect { scope.function_validate_slength(["moo","monkey"]) }.to(raise_error(Puppet::ParseError, /please pass a positive number as max_length/))
  end

  it "should raise a ParseError if argument 2 converted, but to 0" do
    expect { scope.function_validate_slength(["moo","0"]) }.to(raise_error(Puppet::ParseError, /please pass a positive number as max_length/))
  end

  it "should fail if string greater then size" do
    expect { scope.function_validate_slength(["test", 2]) }.to(raise_error(Puppet::ParseError, /It should have been less than or equal to/))
  end

  it "should fail if you pass an array of something other than strings" do
    expect { scope.function_validate_slength([["moo",["moo"],Hash.new["moo" => 7]], 7]) }.to(raise_error(Puppet::ParseError, /is not a string, it's a/))
  end

  it "should fail if you pass something other than a string or array" do
    expect { scope.function_validate_slength([Hash.new["moo" => "7"],6]) }.to(raise_error(Puppet::ParseError), /please pass a string, or an array of strings/)
  end

  it "should not fail if string is smaller or equal to size" do
    expect { scope.function_validate_slength(["test", 5]) }.to_not(raise_error(Puppet::ParseError))
  end

  it "should not fail if array of string is are all smaller or equal to size" do
    expect { scope.function_validate_slength([["moo","foo","bar"], 5]) }.to_not(raise_error(Puppet::ParseError))
  end
end
