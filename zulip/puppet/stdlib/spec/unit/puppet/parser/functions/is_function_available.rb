#!/usr/bin/env rspec
require 'spec_helper'

describe "the is_function_available function" do
  before :all do
    Puppet::Parser::Functions.autoloader.loadall
  end

  before :each do
    @scope = Puppet::Parser::Scope.new
  end

  it "should exist" do
    Puppet::Parser::Functions.function("is_function_available").should == "function_is_function_available"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { @scope.function_is_function_available([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should return false if a nonexistent function is passed" do
    result = @scope.function_is_function_available(['jeff_mccunes_left_sock'])
    result.should(eq(false))
  end

  it "should return true if an available function is passed" do
    result = @scope.function_is_function_available(['require'])
    result.should(eq(true))
  end

end
