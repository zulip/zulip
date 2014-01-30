#
#  downcase.rb
#

module Puppet::Parser::Functions
  newfunction(:downcase, :type => :rvalue, :doc => <<-EOS
Converts the case of a string or all strings in an array to lower case.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "downcase(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'downcase(): Requires either ' +
        'array or string to work with')
    end

    if value.is_a?(Array)
      # Numbers in Puppet are often string-encoded which is troublesome ...
      result = value.collect { |i| i.is_a?(String) ? i.downcase : i }
    else
      result = value.downcase
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
