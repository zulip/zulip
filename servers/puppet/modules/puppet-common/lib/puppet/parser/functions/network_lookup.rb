module Puppet::Parser::Functions
  newfunction(:network_lookup, :type => :rvalue) do |args|
    case args[0]
      when "ip" then
        IPSocket::getaddress(lookupvar('fqdn'))
      when "netmask" then
        "255.255.255.0"
      when "gateway" then
        IPSocket::getaddress(lookupvar('fqdn')).gsub(/\.\d+$/, '.1')
    end
  end
end
