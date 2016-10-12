#
# is_integer.rb
#

module Puppet::Parser::Functions
  newfunction(:is_integer, :type => :rvalue, :doc => <<-EOS
Returns true if the variable returned to this string is an integer.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "is_integer(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    value = arguments[0]

    if value != value.to_i.to_s and !value.is_a? Fixnum then
      return false
    else
      return true
    end

  end
end

# vim: set ts=2 sw=2 et :
