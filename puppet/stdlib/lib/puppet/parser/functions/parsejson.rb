#
# parsejson.rb
#

module Puppet::Parser::Functions
  newfunction(:parsejson, :type => :rvalue, :doc => <<-EOS
This function accepts JSON as a string and converts into the correct Puppet
structure.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "parsejson(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    json = arguments[0]

    # PSON is natively available in puppet
    PSON.load(json)
  end
end

# vim: set ts=2 sw=2 et :
