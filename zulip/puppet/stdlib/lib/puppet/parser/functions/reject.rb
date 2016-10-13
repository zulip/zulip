#
# reject.rb
#

module Puppet::Parser::Functions
  newfunction(:reject, :type => :rvalue, :doc => <<-EOS) do |args|
This function searches through an array and rejects all elements that match
the provided regular expression.

*Examples:*

    reject(['aaa','bbb','ccc','aaaddd'], 'aaa')

Would return:

    ['bbb','ccc']
EOS

    if (args.size != 2)
      raise Puppet::ParseError,
        "reject(): Wrong number of arguments given #{args.size} for 2"
    end

    ary = args[0]
    pattern = Regexp.new(args[1])

    ary.reject { |e| e =~ pattern }
  end
end

# vim: set ts=2 sw=2 et :
