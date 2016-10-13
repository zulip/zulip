#
#  strip.rb
#

module Puppet::Parser::Functions
  newfunction(:strip, :type => :rvalue, :doc => <<-EOS
This function removes leading and trailing whitespace from a string or from
every string inside an array.

*Examples:*

    strip("    aaa   ")

Would result in: "aaa"
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "strip(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'strip(): Requires either ' +
        'array or string to work with')
    end

    if value.is_a?(Array)
      result = value.collect { |i| i.is_a?(String) ? i.strip : i }
    else
      result = value.strip
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
