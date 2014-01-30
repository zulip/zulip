#
# type.rb
#

module Puppet::Parser::Functions
  newfunction(:type, :type => :rvalue, :doc => <<-EOS
Returns the type when passed a variable. Type can be one of:

* string
* array
* hash
* float
* integer
* boolean
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "type(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]

    klass = value.class

    if not [TrueClass, FalseClass, Array, Bignum, Fixnum, Float, Hash, String].include?(klass)
      raise(Puppet::ParseError, 'type(): Unknown type')
    end

    klass = klass.to_s # Ugly ...

    # We note that Integer is the parent to Bignum and Fixnum ...
    result = case klass
      when /^(?:Big|Fix)num$/ then 'integer'
      when /^(?:True|False)Class$/ then 'boolean'
      else klass
    end

    if result == "String" then
      if value == value.to_i.to_s then
        result = "Integer"
      elsif value == value.to_f.to_s then
        result = "Float"
      end
    end

    return result.downcase
  end
end

# vim: set ts=2 sw=2 et :
