require 'rspec'

class Object
  # This is necessary because the RAL has a 'should'
  # method.
  alias :must :should
  alias :must_not :should_not
end
