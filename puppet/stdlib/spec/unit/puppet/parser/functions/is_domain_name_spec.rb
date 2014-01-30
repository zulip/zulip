#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the is_domain_name function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("is_domain_name").should == "function_is_domain_name"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_is_domain_name([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return true if a valid short domain name" do
    result = scope.function_is_domain_name(["x.com"])
    result.should(be_true)
  end

  it "should return true if the domain is ." do
    result = scope.function_is_domain_name(["."])
    result.should(be_true)
  end

  it "should return true if the domain is x.com." do
    result = scope.function_is_domain_name(["x.com."])
    result.should(be_true)
  end

  it "should return true if a valid domain name" do
    result = scope.function_is_domain_name(["foo.bar.com"])
    result.should(be_true)
  end

  it "should allow domain parts to start with numbers" do
    result = scope.function_is_domain_name(["3foo.2bar.com"])
    result.should(be_true)
  end

  it "should allow domain to end with a dot" do
    result = scope.function_is_domain_name(["3foo.2bar.com."])
    result.should(be_true)
  end

  it "should allow a single part domain" do
    result = scope.function_is_domain_name(["orange"])
    result.should(be_true)
  end

  it "should return false if domain parts start with hyphens" do
    result = scope.function_is_domain_name(["-3foo.2bar.com"])
    result.should(be_false)
  end

  it "should return true if domain contains hyphens" do
    result = scope.function_is_domain_name(["3foo-bar.2bar-fuzz.com"])
    result.should(be_true)
  end

  it "should return false if domain name contains spaces" do
    result = scope.function_is_domain_name(["not valid"])
    result.should(be_false)
  end
end
