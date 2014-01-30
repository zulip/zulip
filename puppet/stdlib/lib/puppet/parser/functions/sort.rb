#
# sort.rb
#

module Puppet::Parser::Functions
  newfunction(:sort, :type => :rvalue, :doc => <<-EOS
Sorts strings and arrays lexically.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "sort(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    value = arguments[0]

    if value.is_a?(Array) then
      value.sort
    elsif value.is_a?(String) then
      value.split("").sort.join("")
    end

  end
end

# vim: set ts=2 sw=2 et :
