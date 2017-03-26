require 'spec_helper_system'

describe 'basic tests:' do
  # Using puppet_apply as a subject
  context puppet_apply 'notice("foo")' do
    its(:stdout) { should =~ /foo/ }
    its(:stderr) { should be_empty }
    its(:exit_code) { should be_zero }
  end
end
