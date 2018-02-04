#
# upcase.rb
#

module Puppet::Parser::Functions
  newfunction(:upcase, :type => :rvalue, :doc => <<-EOS
Converts a string or an array of strings to uppercase.

*Examples:*

    upcase("abcd")

Will return:

    ASDF
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "upcase(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'upcase(): Requires either ' +
        'array or string to work with')
    end

    if value.is_a?(Array)
      # Numbers in Puppet are often string-encoded which is troublesome ...
      result = value.collect { |i| i.is_a?(String) ? i.upcase : i }
    else
      result = value.upcase
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
