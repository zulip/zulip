#
#  uriescape.rb
#
require 'uri'

module Puppet::Parser::Functions
  newfunction(:uriescape, :type => :rvalue, :doc => <<-EOS
    Urlencodes a string or array of strings.
    Requires either a single string or an array as an input.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "uriescape(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class
    unsafe = ":/?#[]@!$&'()*+,;= "

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'uriescape(): Requires either ' +
        'array or string to work with')
    end

    if value.is_a?(Array)
      # Numbers in Puppet are often string-encoded which is troublesome ...
      result = value.collect { |i| i.is_a?(String) ? URI.escape(i,unsafe) : i }
    else
      result = URI.escape(value,unsafe)
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
