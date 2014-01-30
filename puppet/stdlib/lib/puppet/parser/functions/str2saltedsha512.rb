#
# str2saltedsha512.rb
#

module Puppet::Parser::Functions
  newfunction(:str2saltedsha512, :type => :rvalue, :doc => <<-EOS
This converts a string to a salted-SHA512 password hash (which is used for
OS X versions >= 10.7). Given any simple string, you will get a hex version
of a salted-SHA512 password hash that can be inserted into your Puppet
manifests as a valid password attribute.
    EOS
  ) do |arguments|
    require 'digest/sha2'

    raise(Puppet::ParseError, "str2saltedsha512(): Wrong number of arguments " +
      "passed (#{arguments.size} but we require 1)") if arguments.size != 1

    password = arguments[0]

    unless password.is_a?(String)
      raise(Puppet::ParseError, 'str2saltedsha512(): Requires a ' +
        "String argument, you passed: #{password.class}")
    end

    seedint    = rand(2**31 - 1)
    seedstring = Array(seedint).pack("L")
    saltedpass = Digest::SHA512.digest(seedstring + password)
    (seedstring + saltedpass).unpack('H*')[0]
  end
end

# vim: set ts=2 sw=2 et :
