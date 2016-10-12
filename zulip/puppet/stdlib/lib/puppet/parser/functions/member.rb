#
# member.rb
#

# TODO(Krzysztof Wilczynski): We need to add support for regular expression ...
# TODO(Krzysztof Wilczynski): Support for strings and hashes too ...

module Puppet::Parser::Functions
  newfunction(:member, :type => :rvalue, :doc => <<-EOS
This function determines if a variable is a member of an array.

*Examples:*

    member(['a','b'], 'b')

Would return: true

    member(['a','b'], 'c')

Would return: false
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "member(): Wrong number of arguments " +
      "given (#{arguments.size} for 2)") if arguments.size < 2

    array = arguments[0]

    unless array.is_a?(Array)
      raise(Puppet::ParseError, 'member(): Requires array to work with')
    end

    item = arguments[1]

    raise(Puppet::ParseError, 'member(): You must provide item ' +
      'to search for within array given') if item.empty?

    result = array.include?(item)

    return result
  end
end

# vim: set ts=2 sw=2 et :
