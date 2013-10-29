module Puppet::Parser::Functions
	# thin wrapper around the ruby gsub function
	# gsub($string, $pattern, $replacement) will replace all occurrences of
	# $pattern in $string with $replacement. $string can be either a singel
	# value or an array. In the latter case, each element of the array will
	# be processed in turn.
	newfunction(:gsub, :type => :rvalue) do |args|
		if args[0].is_a?(Array)
			args[0].collect do |val|
				val.gsub(/#{args[1]}/, args[2])
			end
		else
			args[0].gsub(/#{args[1]}/, args[2])
		end
	end
end

