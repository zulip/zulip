#
# any2array.rb
#

module Puppet::Parser::Functions
  newfunction(:any2array, :type => :rvalue, :doc => <<-EOS
This converts any object to an array containing that object. Empty argument
lists are converted to an empty array. Arrays are left untouched. Hashes are
converted to arrays of alternating keys and values.
    EOS
  ) do |arguments|

    if arguments.empty?
        return []
    end

    if arguments.length == 1
        if arguments[0].kind_of?(Array)
            return arguments[0]
        elsif arguments[0].kind_of?(Hash)
            result = []
            arguments[0].each do |key, value|
                result << key << value
            end
            return result
        end
    end

    return arguments
  end
end

# vim: set ts=2 sw=2 et :
