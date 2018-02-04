#
# values_at.rb
#

module Puppet::Parser::Functions
  newfunction(:values_at, :type => :rvalue, :doc => <<-EOS
Finds value inside an array based on location.

The first argument is the array you want to analyze, and the second element can
be a combination of:

* A single numeric index
* A range in the form of 'start-stop' (eg. 4-9)
* An array combining the above

*Examples*:

    values_at(['a','b','c'], 2)

Would return ['c'].

    values_at(['a','b','c'], ["0-1"])

Would return ['a','b'].

    values_at(['a','b','c','d','e'], [0, "2-3"])

Would return ['a','c','d'].
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "values_at(): Wrong number of " +
      "arguments given (#{arguments.size} for 2)") if arguments.size < 2

    array = arguments.shift

    unless array.is_a?(Array)
      raise(Puppet::ParseError, 'values_at(): Requires array to work with')
    end

    indices = [arguments.shift].flatten() # Get them all ... Pokemon ...

    if not indices or indices.empty?
      raise(Puppet::ParseError, 'values_at(): You must provide ' +
        'at least one positive index to collect')
    end

    result       = []
    indices_list = []

    indices.each do |i|
      if m = i.match(/^(\d+)(\.\.\.?|\-)(\d+)$/)
        start = m[1].to_i
        stop  = m[3].to_i

        type = m[2]

        if start > stop
          raise(Puppet::ParseError, 'values_at(): Stop index in ' +
            'given indices range is smaller than the start index')
        elsif stop > array.size - 1 # First element is at index 0 is it not?
          raise(Puppet::ParseError, 'values_at(): Stop index in ' +
            'given indices range exceeds array size')
        end

        range = case type
          when /^(\.\.|\-)$/ then (start .. stop)
          when /^(\.\.\.)$/  then (start ... stop) # Exclusive of last element ...
        end

        range.each { |i| indices_list << i.to_i }
      else
        # Only positive numbers allowed in this case ...
        if not i.match(/^\d+$/)
          raise(Puppet::ParseError, 'values_at(): Unknown format ' +
            'of given index')
        end

        # In Puppet numbers are often string-encoded ...
        i = i.to_i

        if i > array.size - 1 # Same story.  First element is at index 0 ...
          raise(Puppet::ParseError, 'values_at(): Given index ' +
            'exceeds array size')
        end

        indices_list << i
      end
    end

    # We remove nil values as they make no sense in Puppet DSL ...
    result = indices_list.collect { |i| array[i] }.compact

    return result
  end
end

# vim: set ts=2 sw=2 et :
