# Test whether a given class or definition is defined
require 'puppet/parser/functions'

Puppet::Parser::Functions.newfunction(:getparam,
                                      :type => :rvalue,
                                      :doc => <<-'ENDOFDOC'
Takes a resource reference and name of the parameter and
returns value of resource's parameter.

*Examples:*

    define example_resource($param) {
    }

    example_resource { "example_resource_instance":
        param => "param_value"
    }

    getparam(Example_resource["example_resource_instance"], "param")

Would return: param_value
ENDOFDOC
) do |vals|
  reference, param = vals
  raise(ArgumentError, 'Must specify a reference') unless reference
  raise(ArgumentError, 'Must specify name of a parameter') unless param and param.instance_of? String

  return '' if param.empty?

  if resource = findresource(reference.to_s)
    return resource[param] if resource[param]
  end

  return ''
end
