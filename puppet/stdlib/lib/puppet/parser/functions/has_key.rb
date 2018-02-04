module Puppet::Parser::Functions

  newfunction(:has_key, :type => :rvalue, :doc => <<-'ENDHEREDOC') do |args|
    Determine if a hash has a certain key value.

    Example:

        $my_hash = {'key_one' => 'value_one'}
        if has_key($my_hash, 'key_two') {
          notice('we will not reach here')
        }
        if has_key($my_hash, 'key_one') {
          notice('this will be printed')
        }

    ENDHEREDOC

    unless args.length == 2
      raise Puppet::ParseError, ("has_key(): wrong number of arguments (#{args.length}; must be 2)")
    end
    unless args[0].is_a?(Hash)
      raise Puppet::ParseError, "has_key(): expects the first argument to be a hash, got #{args[0].inspect} which is of type #{args[0].class}"
    end
    args[0].has_key?(args[1])

  end

end
