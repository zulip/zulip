# prefix arguments 2..n with first argument

module Puppet::Parser::Functions
	newfunction(:prefix_with, :type => :rvalue) do |args|
		prefix = args.shift
		args.collect {|v| "%s%s" % [prefix, v] }
	end
end

