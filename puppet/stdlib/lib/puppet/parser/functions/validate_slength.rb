module Puppet::Parser::Functions

  newfunction(:validate_slength, :doc => <<-'ENDHEREDOC') do |args|
    Validate that the first argument is a string (or an array of strings), and
    less/equal to than the length of the second argument.  It fails if the first
    argument is not a string or array of strings, and if arg 2 is not convertable
    to a number.

    The following values will pass:

      validate_slength("discombobulate",17)
      validate_slength(["discombobulate","moo"],17)

    The following valueis will not:

      validate_slength("discombobulate",1)
      validate_slength(["discombobulate","thermometer"],5)

    ENDHEREDOC

    raise Puppet::ParseError, ("validate_slength(): Wrong number of arguments (#{args.length}; must be = 2)") unless args.length == 2

    unless (args[0].is_a?(String) or args[0].is_a?(Array))
      raise Puppet::ParseError, ("validate_slength(): please pass a string, or an array of strings - what you passed didn't work for me at all - #{args[0].class}")
    end

    begin
      max_length = args[1].to_i
    rescue NoMethodError => e
      raise Puppet::ParseError, ("validate_slength(): Couldn't convert whatever you passed as the length parameter to an integer  - sorry: " + e.message )
    end

    raise Puppet::ParseError, ("validate_slength(): please pass a positive number as max_length") unless max_length > 0

    case args[0]
      when String
        raise Puppet::ParseError, ("validate_slength(): #{args[0].inspect} is #{args[0].length} characters.  It should have been less than or equal to #{max_length} characters") unless args[0].length <= max_length
      when Array
        args[0].each do |arg|
          if arg.is_a?(String)
            unless ( arg.is_a?(String) and arg.length <= max_length )
              raise Puppet::ParseError, ("validate_slength(): #{arg.inspect} is #{arg.length} characters.  It should have been less than or equal to #{max_length} characters")
            end
          else
            raise Puppet::ParseError, ("validate_slength(): #{arg.inspect} is not a string, it's a #{arg.class}")
          end
        end
      else
        raise Puppet::ParseError, ("validate_slength(): please pass a string, or an array of strings - what you passed didn't work for me at all - #{args[0].class}")
    end
  end
end
