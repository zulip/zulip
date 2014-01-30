#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the parseyaml function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("parseyaml").should == "function_parseyaml"
  end

  it "should raise a ParseError if there is less than 1 arguments" do
    lambda { scope.function_parseyaml([]) }.should( raise_error(Puppet::ParseError))
  end

  it "should convert YAML to a data structure" do
    yaml = <<-EOS
- aaa
- bbb
- ccc
EOS
    result = scope.function_parseyaml([yaml])
    result.should(eq(['aaa','bbb','ccc']))
  end
end
