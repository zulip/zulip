#
# num2bool.rb
#

module Puppet::Parser::Functions
  newfunction(:num2bool, :type => :rvalue, :doc => <<-EOS
This function converts a number or a string representation of a number into a
true boolean. Zero or anything non-numeric becomes false. Numbers higher then 0
become true.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "num2bool(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size != 1

    number = arguments[0]

    case number
    when Numeric
      # Yay, it's a number
    when String
      begin
        number = Float(number)
      rescue ArgumentError => ex
        raise(Puppet::ParseError, "num2bool(): '#{number}' does not look like a number: #{ex.message}")
      end
    else
      begin
        number = number.to_s
      rescue NoMethodError => ex
        raise(Puppet::ParseError, "num2bool(): Unable to parse argument: #{ex.message}")
      end
    end

    # Truncate Floats
    number = number.to_i

    # Return true for any positive number and false otherwise
    return number > 0
  end
end

# vim: set ts=2 sw=2 et :
