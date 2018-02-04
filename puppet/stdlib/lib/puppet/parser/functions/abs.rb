#
# abs.rb
#

module Puppet::Parser::Functions
  newfunction(:abs, :type => :rvalue, :doc => <<-EOS
    Returns the absolute value of a number, for example -34.56 becomes
    34.56. Takes a single integer and float value as an argument.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "abs(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]

    # Numbers in Puppet are often string-encoded which is troublesome ...
    if value.is_a?(String)
      if value.match(/^-?(?:\d+)(?:\.\d+){1}$/)
        value = value.to_f
      elsif value.match(/^-?\d+$/)
        value = value.to_i
      else
        raise(Puppet::ParseError, 'abs(): Requires float or ' +
          'integer to work with')
      end
    end

    # We have numeric value to handle ...
    result = value.abs

    return result
  end
end

# vim: set ts=2 sw=2 et :
