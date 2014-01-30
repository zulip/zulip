#
# is_numeric.rb
#

module Puppet::Parser::Functions
  newfunction(:is_numeric, :type => :rvalue, :doc => <<-EOS
Returns true if the variable passed to this function is a number.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "is_numeric(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    value = arguments[0]

    if value == value.to_f.to_s or value == value.to_i.to_s or value.is_a? Numeric then
      return true
    else
      return false
    end

  end
end

# vim: set ts=2 sw=2 et :
