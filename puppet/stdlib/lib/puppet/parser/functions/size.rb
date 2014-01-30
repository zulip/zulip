#
# size.rb
#

# TODO(Krzysztof Wilczynski): Support for hashes would be nice too ...

module Puppet::Parser::Functions
  newfunction(:size, :type => :rvalue, :doc => <<-EOS
Returns the number of elements in a string or array.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "size(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    item = arguments[0]

    if item.is_a?(String)

      begin
        #
        # Check whether your item is a numeric value or not ...
        # This will take care about positive and/or negative numbers
        # for both integer and floating-point values ...
        #
        # Please note that Puppet has no notion of hexadecimal
        # nor octal numbers for its DSL at this point in time ...
        #
        Float(item)

        raise(Puppet::ParseError, 'size(): Requires either ' +
          'string or array to work with')

      rescue ArgumentError
        result = item.size
      end

    elsif item.is_a?(Array)
      result = item.size
    else
      raise(Puppet::ParseError, 'size(): Unknown type given')
    end

    return result
  end
end

# vim: set ts=2 sw=2 et :
