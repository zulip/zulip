source "https://rubygems.org"

def location_for(place, fake_version = nil)
  mdata = /^(git:[^#]*)#(.*)/.match(place)
  if mdata
    [fake_version, { :git => mdata[1], :branch => mdata[2], :require => false }].compact
  elsif place =~ /^file:\/\/(.*)/
    ['>= 0', { :path => File.expand_path(mdata[1]), :require => false }]
  else
    [place, { :require => false }]
  end
end

group :development do
  gem 'watchr'
end

group :development, :test do
  gem 'rake'
  gem 'puppetmodule-stdlib', ">= 1.0.0", :path => File.expand_path("..", __FILE__)
  gem 'rspec', "~> 2.11.0", :require => false
  gem 'mocha', "~> 0.10.5", :require => false
  gem 'puppetlabs_spec_helper', :require => false
  gem 'rspec-puppet', :require => false
end

facterversion = ENV['GEM_FACTER_VERSION']
if facterversion
  gem 'facter', *location_for(facterversion)
else
  gem 'facter', :require => false
end

ENV['GEM_PUPPET_VERSION'] ||= ENV['PUPPET_GEM_VERSION']
puppetversion = ENV['GEM_PUPPET_VERSION']
if puppetversion
  gem 'puppet', *location_for(puppetversion)
else
  gem 'puppet', :require => false
end

# vim:ft=ruby
