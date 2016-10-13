#
# flatten.rb
#

module Puppet::Parser::Functions
  newfunction(:flatten, :type => :rvalue, :doc => <<-EOS
This function flattens any deeply nested arrays and returns a single flat array
as a result.

*Examples:*

    flatten(['a', ['b', ['c']]])

Would return: ['a','b','c']
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "flatten(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size != 1

    array = arguments[0]

    unless array.is_a?(Array)
      raise(Puppet::ParseError, 'flatten(): Requires array to work with')
    end

    result = array.flatten

    return result
  end
end

# vim: set ts=2 sw=2 et :
