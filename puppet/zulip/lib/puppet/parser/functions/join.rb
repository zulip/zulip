# Taken from https://github.com/puppetlabs/puppetlabs-stdlib/blob/19cdf29f27c3e5005ee441d1ec46d7da27a0f777/lib/puppet/parser/functions/join.rb
#
# join.rb
#
module Puppet::Parser::Functions
  newfunction(:join, :type => :rvalue, :doc => <<-DOC
    This function joins an array into a string using a separator.

    *Examples:*

        join(['a','b','c'], ",")

    Would result in: "a,b,c"

    Note: from Puppet 5.4.0, the compatible function with the same name in Puppet core
    will be used instead of this function.
    DOC
             ) do |arguments|

    # Technically we support two arguments but only first is mandatory ...
    raise(Puppet::ParseError, "join(): Wrong number of arguments given (#{arguments.size} for 1)") if arguments.empty?

    array = arguments[0]

    unless array.is_a?(Array)
      raise(Puppet::ParseError, 'join(): Requires array to work with')
    end

    suffix = arguments[1] if arguments[1]

    if suffix
      unless suffix.is_a?(String)
        raise(Puppet::ParseError, 'join(): Requires string to work with')
      end
    end

    result = suffix ? array.join(suffix) : array.join

    return result
  end
end

# vim: set ts=2 sw=2 et :
