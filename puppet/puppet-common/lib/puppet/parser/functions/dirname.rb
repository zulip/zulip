# dirname(string) : string
# dirname(string[]) : string[]
#
# Returns all components of the filename given as argument except the last
# one. The filename must be formed using forward slashes (``/..) regardless of
# the separator used on the local file system.
module Puppet::Parser::Functions
	newfunction(:dirname, :type => :rvalue) do |args|
		if args[0].is_a?(Array)
			args.collect do |a| File.dirname(a) end
		else
			File.dirname(args[0])
		end
	end
end

