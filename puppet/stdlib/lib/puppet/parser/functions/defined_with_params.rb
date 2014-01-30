# Test whether a given class or definition is defined
require 'puppet/parser/functions'

Puppet::Parser::Functions.newfunction(:defined_with_params,
                                      :type => :rvalue,
                                      :doc => <<-'ENDOFDOC'
Takes a resource reference and an optional hash of attributes.

Returns true if a resource with the specified attributes has already been added
to the catalog, and false otherwise.

    user { 'dan':
      ensure => present,
    }

    if ! defined_with_params(User[dan], {'ensure' => 'present' }) {
      user { 'dan': ensure => present, }
    }
ENDOFDOC
) do |vals|
  reference, params = vals
  raise(ArgumentError, 'Must specify a reference') unless reference
  if (! params) || params == ''
    params = {}
  end
  ret = false
  if resource = findresource(reference.to_s)
    matches = params.collect do |key, value|
      resource[key] == value
    end
    ret = params.empty? || !matches.include?(false)
  end
  Puppet.debug("Resource #{reference} was not determined to be defined")
  ret
end
