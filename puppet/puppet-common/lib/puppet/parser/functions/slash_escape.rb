# escape slashes in a String
module Puppet::Parser::Functions
	newfunction(:slash_escape, :type => :rvalue) do |args|
		args[0].gsub(/\//, '\\/')
	end
end

