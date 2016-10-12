#
# fqdn_rotate.rb
#

module Puppet::Parser::Functions
  newfunction(:fqdn_rotate, :type => :rvalue, :doc => <<-EOS
Rotates an array a random number of times based on a nodes fqdn.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "fqdn_rotate(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    value = arguments[0]
    klass = value.class
    require 'digest/md5'

    unless [Array, String].include?(klass)
      raise(Puppet::ParseError, 'fqdn_rotate(): Requires either ' +
        'array or string to work with')
    end

    result = value.clone

    string = value.is_a?(String) ? true : false

    # Check whether it makes sense to rotate ...
    return result if result.size <= 1

    # We turn any string value into an array to be able to rotate ...
    result = string ? result.split('') : result

    elements = result.size

    srand(Digest::MD5.hexdigest([lookupvar('::fqdn'),arguments].join(':')).hex)
    rand(elements).times {
       result.push result.shift
    }

    result = string ? result.join : result

    return result
  end
end

# vim: set ts=2 sw=2 et :
