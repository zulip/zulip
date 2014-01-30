require 'spec_helper_system'

describe 'apt::source' do

  context 'reset' do
    it 'clean up puppetlabs repo' do
      shell('apt-key del 4BD6EC30')
      shell('rm /etc/apt/sources.list.d/puppetlabs.list')
    end
  end

  context 'apt::source' do
    it 'should work with no errors' do
      pp = <<-EOS
      include '::apt'
      apt::source { 'puppetlabs':
        location   => 'http://apt.puppetlabs.com',
        repos      => 'main',
        key        => '4BD6EC30',
        key_server => 'pgp.mit.edu',
      }
      EOS

      puppet_apply(pp) do |r|
        r.exit_code.should_not == 1
      end
    end

    describe 'key should exist' do
      it 'finds puppetlabs key' do
        shell('apt-key list | grep 4BD6EC30') do |r|
          r.exit_code.should be_zero
        end
      end
    end

    describe 'source should exist' do
      describe file('/etc/apt/sources.list.d/puppetlabs.list') do
        it { should be_file }
      end
    end
  end

  context 'reset' do
    it 'clean up puppetlabs repo' do
      shell('apt-key del 4BD6EC30')
      shell('rm /etc/apt/sources.list.d/puppetlabs.list')
    end
  end

end
