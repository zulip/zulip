module Puppet::Parser::Functions
  newfunction(:dirname, :type => :rvalue, :doc => <<-EOS
    Returns the dirname of a path.
    EOS
  ) do |arguments|

    raise(Puppet::ParseError, "dirname(): Wrong number of arguments " +
      "given (#{arguments.size} for 1)") if arguments.size < 1

    path = arguments[0]
    return File.dirname(path)
  end
end

# vim: set ts=2 sw=2 et :
