#
# join.rb
#

module Puppet::Parser::Functions
  newfunction(:join_keys_to_values, :type => :rvalue, :doc => <<-EOS
This function joins each key of a hash to that key's corresponding value with a
separator. Keys and values are cast to strings. The return value is an array in
which each element is one joined key/value pair.

*Examples:*

    join_keys_to_values({'a'=>1,'b'=>2}, " is ")

Would result in: ["a is 1","b is 2"]
    EOS
  ) do |arguments|

    # Validate the number of arguments.
    if arguments.size != 2
      raise(Puppet::ParseError, "join_keys_to_values(): Takes exactly two " +
            "arguments, but #{arguments.size} given.")
    end

    # Validate the first argument.
    hash = arguments[0]
    if not hash.is_a?(Hash)
      raise(TypeError, "join_keys_to_values(): The first argument must be a " +
            "hash, but a #{hash.class} was given.")
    end

    # Validate the second argument.
    separator = arguments[1]
    if not separator.is_a?(String)
      raise(TypeError, "join_keys_to_values(): The second argument must be a " +
            "string, but a #{separator.class} was given.")
    end

    # Join the keys to their values.
    hash.map do |k,v|
      String(k) + separator + String(v)
    end

  end
end

# vim: set ts=2 sw=2 et :
