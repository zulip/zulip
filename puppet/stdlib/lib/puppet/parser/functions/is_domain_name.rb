#
# is_domain_name.rb
#

module Puppet::Parser::Functions
  newfunction(:is_domain_name, :type => :rvalue, :doc => <<-EOS
Returns true if the string passed to this function is a syntactically correct domain name.
    EOS
  ) do |arguments|

    if (arguments.size != 1) then
      raise(Puppet::ParseError, "is_domain_name(): Wrong number of arguments "+
        "given #{arguments.size} for 1")
    end

    domain = arguments[0]

    # Limits (rfc1035, 3.1)
    domain_max_length=255
    label_min_length=1
    label_max_length=63

    # Allow ".", it is the top level domain
    return true if domain == '.'

    # Remove the final dot, if present.
    domain.chomp!('.')

    # Check the whole domain
    return false if domain.empty?
    return false if domain.length > domain_max_length

    # Check each label in the domain
    labels = domain.split('.')
    vlabels = labels.each do |label|
      break if label.length < label_min_length
      break if label.length > label_max_length
      break if label[-1..-1] == '-'
      break if label[0..0] == '-'
      break unless /^[a-z\d-]+$/i.match(label)
    end
    return vlabels == labels

  end
end

# vim: set ts=2 sw=2 et :
