# split($string, $delimiter) : $string
# split($string[], $delimiter) : $string[][]
#
# Split the first argument(s) on every $delimiter. $delimiter is interpreted as
# Ruby regular expression.
#
# For long-term portability it is recommended to refrain from using Ruby's
# extended RE features.
module Puppet::Parser::Functions
	newfunction(:split, :type => :rvalue) do |args|
		if args[0].is_a?(Array)
			args.collect do |a| a.split(/#{args[1]}/) end
		else
			args[0].split(/#{args[1]}/)
		end
	end
end
