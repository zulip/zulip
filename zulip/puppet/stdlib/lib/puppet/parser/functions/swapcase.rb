#
#  swapcase.rb
#

module Puppet::Parser::Functions
  newfunction(:swapcase, :type => :rvalue, :doc => <<-EOS
This function will swap the existing case of a string.

*Examples:*

    swapcase("aBcD")

Would result in: "AbCd"
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "swapcase(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'swapcase(): Requires either ' +
        'array or string to work with')
    end

    if value.is_a?(Array)
      # Numbers in Puppet are often string-encoded which is troublesome ...
      result = value.collect { |i| i.is_a?(String) ? i.swapcase : i }
    else
      result = value.swapcase
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
