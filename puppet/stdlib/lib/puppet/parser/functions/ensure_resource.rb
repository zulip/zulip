# Test whether a given class or definition is defined
require 'puppet/parser/functions'

Puppet::Parser::Functions.newfunction(:ensure_resource,
                                      :type => :statement,
                                      :doc => <<-'ENDOFDOC'
Takes a resource type, title, and a list of attributes that describe a
resource.

    user { 'dan':
      ensure => present,
    }

This example only creates the resource if it does not already exist:

    ensure_resource('user, 'dan', {'ensure' => 'present' })

If the resource already exists but does not match the specified parameters,
this function will attempt to recreate the resource leading to a duplicate
resource definition error.

An array of resources can also be passed in and each will be created with
the type and parameters specified if it doesn't already exist.

    ensure_resource('user', ['dan','alex'], {'ensure' => 'present'})

ENDOFDOC
) do |vals|
  type, title, params = vals
  raise(ArgumentError, 'Must specify a type') unless type
  raise(ArgumentError, 'Must specify a title') unless title
  params ||= {}

  items = [title].flatten

  items.each do |item|
    Puppet::Parser::Functions.function(:defined_with_params)
    if function_defined_with_params(["#{type}[#{item}]", params])
      Puppet.debug("Resource #{type}[#{item}] not created because it already exists")
    else
      Puppet::Parser::Functions.function(:create_resources)
      function_create_resources([type.capitalize, { item => params }])
    end
  end
end
