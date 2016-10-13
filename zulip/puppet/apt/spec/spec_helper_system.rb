require 'rspec-system/spec_helper'
require 'rspec-system-puppet/helpers'
require 'rspec-system-serverspec/helpers'

include RSpecSystemPuppet::Helpers

include Serverspec::Helper::RSpecSystem
include Serverspec::Helper::DetectOS

RSpec.configure do |c|
  # Project root
  proj_root = File.expand_path(File.join(File.dirname(__FILE__), '..'))

  # Enable colour
  c.tty = true

  c.include RSpecSystemPuppet::Helpers

  # This is where we 'setup' the nodes before running our tests
  c.before :suite do
    # May as well update here as this can only run on apt-get machines.
    shell('apt-get update')
    # Install puppet
    puppet_install

    # Install modules and dependencies
    puppet_module_install(:source => proj_root, :module_name => 'apt')
    shell('puppet module install puppetlabs-stdlib')
  end
end
