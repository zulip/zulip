#
# delete.rb
#

# TODO(Krzysztof Wilczynski): We need to add support for regular expression ...

module Puppet::Parser::Functions
  newfunction(:delete, :type => :rvalue, :doc => <<-EOS
Deletes all instances of a given element from an array, substring from a
string, or key from a hash.

*Examples:*

    delete(['a','b','c','b'], 'b')
    Would return: ['a','c']

    delete({'a'=>1,'b'=>2,'c'=>3}, 'b')
    Would return: {'a'=>1,'c'=>3}

    delete('abracadabra', 'bra')
    Would return: 'acada'
    EOS
  ) do |arguments|

    if (arguments.size != 2) then
      raise(Puppet::ParseError, "delete(): Wrong number of arguments "+
        "given #{arguments.size} for 2.")
    end

    collection = arguments[0]
    item = arguments[1]

    case collection
    when Array, Hash
      collection.delete item
    when String
      collection.gsub! item, ''
    else
      raise(TypeError, "delete(): First argument must be an Array, " +
            "String, or Hash. Given an argument of class #{collection.class}.")
    end
    collection
  end
end

# vim: set ts=2 sw=2 et :
