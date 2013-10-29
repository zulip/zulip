# apply regexp escaping to a string
module Puppet::Parser::Functions
	newfunction(:re_escape, :type => :rvalue) do |args|
		Regexp.escape(args[0])
	end
end

