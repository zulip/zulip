module Puppet::Parser::Functions

  newfunction(:validate_string, :doc => <<-'ENDHEREDOC') do |args|
    Validate that all passed values are string data structures. Abort catalog
    compilation if any value fails this check.

    The following values will pass:

        $my_string = "one two"
        validate_string($my_string, 'three')

    The following values will fail, causing compilation to abort:

        validate_string(true)
        validate_string([ 'some', 'array' ])
        $undefined = undef
        validate_string($undefined)

    ENDHEREDOC

    unless args.length > 0 then
      raise Puppet::ParseError, ("validate_string(): wrong number of arguments (#{args.length}; must be > 0)")
    end

    args.each do |arg|
      unless arg.is_a?(String)
        raise Puppet::ParseError, ("#{arg.inspect} is not a string.  It looks to be a #{arg.class}")
      end
    end

  end

end
