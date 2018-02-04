#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe "the str2saltedsha512 function" do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  it "should exist" do
    Puppet::Parser::Functions.function("str2saltedsha512").should == "function_str2saltedsha512"
  end

  it "should raise a ParseError if there is less than 1 argument" do
    expect { scope.function_str2saltedsha512([]) }.to( raise_error(Puppet::ParseError) )
  end

  it "should raise a ParseError if there is more than 1 argument" do
    expect { scope.function_str2saltedsha512(['foo', 'bar', 'baz']) }.to( raise_error(Puppet::ParseError) )
  end

  it "should return a salted-sha512 password hash 136 characters in length" do
    result = scope.function_str2saltedsha512(["password"])
    result.length.should(eq(136))
  end

  it "should raise an error if you pass a non-string password" do
    expect { scope.function_str2saltedsha512([1234]) }.to( raise_error(Puppet::ParseError) )
  end

  it "should generate a valid password" do
    # Allow the function to generate a password based on the string 'password'
    password_hash = scope.function_str2saltedsha512(["password"])

    # Separate the Salt and Password from the Password Hash
    salt     = password_hash[0..7]
    password = password_hash[8..-1]

    # Convert the Salt and Password from Hex to Binary Data
    str_salt     = Array(salt.lines).pack('H*')
    str_password = Array(password.lines).pack('H*')

    # Combine the Binary Salt with 'password' and compare the end result
    saltedpass    = Digest::SHA512.digest(str_salt + 'password')
    result        = (str_salt + saltedpass).unpack('H*')[0]
    result.should == password_hash
  end
end
