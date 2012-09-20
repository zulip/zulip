# get an uniq array of ipaddresses for a hostname
require 'resolv'

module Puppet::Parser::Functions
	newfunction(:hostname, :type => :rvalue) do |args|
        res = Array.new
        Resolv::DNS.new.each_address(args[0]){ |addr|
            res << addr
        }
        res.uniq
	end
end

