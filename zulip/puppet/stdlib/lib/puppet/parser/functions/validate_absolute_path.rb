module Puppet::Parser::Functions
  newfunction(:validate_absolute_path, :doc => <<-'ENDHEREDOC') do |args|
    Validate the string represents an absolute path in the filesystem.  This function works
    for windows and unix style paths.

    The following values will pass:

        $my_path = "C:/Program Files (x86)/Puppet Labs/Puppet"
        validate_absolute_path($my_path)
        $my_path2 = "/var/lib/puppet"
        validate_absolute_path($my_path2)


    The following values will fail, causing compilation to abort:

        validate_absolute_path(true)
        validate_absolute_path([ 'var/lib/puppet', '/var/foo' ])
        validate_absolute_path([ '/var/lib/puppet', 'var/foo' ])
        $undefined = undef
        validate_absolute_path($undefined)

    ENDHEREDOC

    require 'puppet/util'

    unless args.length > 0 then
      raise Puppet::ParseError, ("validate_absolute_path(): wrong number of arguments (#{args.length}; must be > 0)")
    end

    args.each do |arg|
      # This logic was borrowed from
      # [lib/puppet/file_serving/base.rb](https://github.com/puppetlabs/puppet/blob/master/lib/puppet/file_serving/base.rb)

      # Puppet 2.7 and beyond will have Puppet::Util.absolute_path?  Fall back to a back-ported implementation otherwise.
      if Puppet::Util.respond_to?(:absolute_path?) then
        unless Puppet::Util.absolute_path?(arg, :posix) or Puppet::Util.absolute_path?(arg, :windows)
          raise Puppet::ParseError, ("#{arg.inspect} is not an absolute path.")
        end
      else
        # This code back-ported from 2.7.x's lib/puppet/util.rb Puppet::Util.absolute_path?
        # Determine in a platform-specific way whether a path is absolute. This
        # defaults to the local platform if none is specified.
        # Escape once for the string literal, and once for the regex.
        slash = '[\\\\/]'
        name = '[^\\\\/]+'
        regexes = {
          :windows => %r!^(([A-Z]:#{slash})|(#{slash}#{slash}#{name}#{slash}#{name})|(#{slash}#{slash}\?#{slash}#{name}))!i,
          :posix   => %r!^/!,
        }

        rval = (!!(arg =~ regexes[:posix])) || (!!(arg =~ regexes[:windows]))
        rval or raise Puppet::ParseError, ("#{arg.inspect} is not an absolute path.")
      end
    end
  end
end
