#
# zip.rb
#

module Puppet::Parser::Functions
  newfunction(:zip, :type => :rvalue, :doc => <<-EOS
Takes one element from first array and merges corresponding elements from second array. This generates a sequence of n-element arrays, where n is one more than the count of arguments.

*Example:*

    zip(['1','2','3'],['4','5','6'])

Would result in:

    ["1", "4"], ["2", "5"], ["3", "6"]
    EOS
  ) do |arguments|

    # Technically we support three arguments but only first is mandatory ...
    raise(Puppet::ParseError, "zip(): Wrong number of arguments " +
      "given (#{arguments.size} for 2)") if arguments.size < 2

    a = arguments[0]
    b = arguments[1]

    unless a.is_a?(Array) and b.is_a?(Array)
      raise(Puppet::ParseError, 'zip(): Requires array to work with')
    end

    flatten = arguments[2] if arguments[2]

    if flatten
      klass = flatten.class

      # We can have either true or false, or string which resembles boolean ...
      unless [FalseClass, TrueClass, String].include?(klass)
        raise(Puppet::ParseError, 'zip(): Requires either ' +
          'boolean or string to work with')
      end

      if flatten.is_a?(String)
        # We consider all the yes, no, y, n and so on too ...
        flatten = case flatten
          #
          # This is how undef looks like in Puppet ...
          # We yield false in this case.
          #
          when /^$/, '' then false # Empty string will be false ...
          when /^(1|t|y|true|yes)$/  then true
          when /^(0|f|n|false|no)$/  then false
          when /^(undef|undefined)$/ then false # This is not likely to happen ...
          else
            raise(Puppet::ParseError, 'zip(): Unknown type of boolean given')
        end
      end
    end

    result = a.zip(b)
    result = flatten ? result.flatten : result

    return result
  end
end

# vim: set ts=2 sw=2 et :
