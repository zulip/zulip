#
# is_mac_address.rb
#

module Puppet::Parser::Functions
  newfunction(:is_mac_address, :type => :rvalue, :doc => <<-EOS
Returns true if the string passed to this function is a valid mac address.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "is_mac_address(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    mac = arguments[0]

    if /^[a-fA-F0-9]{1,2}:[a-fA-F0-9]{1,2}:[a-fA-F0-9]{1,2}:[a-fA-F0-9]{1,2}:[a-fA-F0-9]{1,2}:[a-fA-F0-9]{1,2}$/.match(mac) then
      return true
    else
      return false
    end

  end
end

# vim: set ts=2 sw=2 et :
