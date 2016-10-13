module Puppet::Parser::Functions

  newfunction(:validate_array, :doc => <<-'ENDHEREDOC') do |args|
    Validate that all passed values are array data structures. Abort catalog
    compilation if any value fails this check.

    The following values will pass:

        $my_array = [ 'one', 'two' ]
        validate_array($my_array)

    The following values will fail, causing compilation to abort:

        validate_array(true)
        validate_array('some_string')
        $undefined = undef
        validate_array($undefined)

    ENDHEREDOC

    unless args.length > 0 then
      raise Puppet::ParseError, ("validate_array(): wrong number of arguments (#{args.length}; must be > 0)")
    end

    args.each do |arg|
      unless arg.is_a?(Array)
        raise Puppet::ParseError, ("#{arg.inspect} is not an Array.  It looks to be a #{arg.class}")
      end
    end

  end

end
