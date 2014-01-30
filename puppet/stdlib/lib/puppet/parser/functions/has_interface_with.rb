#
# has_interface_with
#

module Puppet::Parser::Functions
  newfunction(:has_interface_with, :type => :rvalue, :doc => <<-EOS
Returns boolean based on kind and value:
  * macaddress
  * netmask
  * ipaddress
  * network

has_interface_with("macaddress", "x:x:x:x:x:x")
has_interface_with("ipaddress", "127.0.0.1")    => true
etc.

If no "kind" is given, then the presence of the interface is checked:
has_interface_with("lo")                        => true
    EOS
  ) do |args|

    raise(Puppet::ParseError, "has_interface_with(): Wrong number of arguments " +
          "given (#{args.size} for 1 or 2)") if args.size < 1 or args.size > 2

    interfaces = lookupvar('interfaces')

    # If we do not have any interfaces, then there are no requested attributes
    return false if (interfaces == :undefined)

    interfaces = interfaces.split(',')

    if args.size == 1
      return interfaces.member?(args[0])
    end

    kind, value = args

    if lookupvar(kind) == value
      return true
    end

    result = false
    interfaces.each do |iface|
      if value == lookupvar("#{kind}_#{iface}")
        result = true
        break
      end
    end

    result
  end
end
