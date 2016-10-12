module Puppet::Parser::Functions

  newfunction(:validate_bool, :doc => <<-'ENDHEREDOC') do |args|
    Validate that all passed values are either true or false. Abort catalog
    compilation if any value fails this check.

    The following values will pass:

        $iamtrue = true
        validate_bool(true)
        validate_bool(true, true, false, $iamtrue)

    The following values will fail, causing compilation to abort:

        $some_array = [ true ]
        validate_bool("false")
        validate_bool("true")
        validate_bool($some_array)

    ENDHEREDOC

    unless args.length > 0 then
      raise Puppet::ParseError, ("validate_bool(): wrong number of arguments (#{args.length}; must be > 0)")
    end

    args.each do |arg|
      unless (arg.is_a?(TrueClass) || arg.is_a?(FalseClass))
        raise Puppet::ParseError, ("#{arg.inspect} is not a boolean.  It looks to be a #{arg.class}")
      end
    end

  end

end
