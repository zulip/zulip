# subsititute($string, $regex, $replacement) : $string
# subsititute($string[], $regex, $replacement) : $string[]
#
# Replace all ocurrences of $regex in $string by $replacement.
# $regex is interpreted as Ruby regular expression.
#
# For long-term portability it is recommended to refrain from using Ruby's
# extended RE features.
module Puppet::Parser::Functions
	newfunction(:substitute, :type => :rvalue) do |args|
		if args[0].is_a?(Array)
			args[0].collect do |val|
				val.gsub(/#{args[1]}/, args[2])
			end
		else
			args[0].gsub(/#{args[1]}/, args[2])
		end
	end
end

