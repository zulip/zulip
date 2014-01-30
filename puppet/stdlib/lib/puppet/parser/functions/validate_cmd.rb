require 'puppet/util/execution'

module Puppet::Parser::Functions
  newfunction(:validate_cmd, :doc => <<-'ENDHEREDOC') do |args|
    Perform validation of a string with an external command.
    The first argument of this function should be a string to
    test, and the second argument should be a path to a test command
    taking a file as last argument. If the command, launched against
    a tempfile containing the passed string, returns a non-null value,
    compilation will abort with a parse error.

    If a third argument is specified, this will be the error message raised and
    seen by the user.

    A helpful error message can be returned like this:

    Example:

        validate_cmd($sudoerscontent, '/usr/sbin/visudo -c -f', 'Visudo failed to validate sudoers content')

    ENDHEREDOC
    if (args.length < 2) or (args.length > 3) then
      raise Puppet::ParseError, ("validate_cmd(): wrong number of arguments (#{args.length}; must be 2 or 3)")
    end

    msg = args[2] || "validate_cmd(): failed to validate content with command #{args[1].inspect}"

    content = args[0]
    checkscript = args[1]

    # Test content in a temporary file
    tmpfile = Tempfile.new("validate_cmd")
    begin
      tmpfile.write(content)
      if Puppet::Util::Execution.respond_to?('execute')
        Puppet::Util::Execution.execute("#{checkscript} #{tmpfile.path}")
      else
        Puppet::Util.execute("#{checkscript} #{tmpfile.path}")
      end
    rescue Puppet::ExecutionFailure => detail
      msg += "\n#{detail}"
      raise Puppet::ParseError, msg
    ensure
      tmpfile.unlink
    end
  end
end
