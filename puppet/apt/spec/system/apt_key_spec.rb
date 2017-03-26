require 'spec_helper_system'

describe 'apt::key' do

  context 'reset' do
    it 'clean up keys' do
      shell('apt-key del 4BD6EC30')
      shell('apt-key del D50582E6')
    end
  end

  context 'apt::key' do
    it 'should work with no errors' do
      pp = <<-EOS
      include '::apt'
      apt::key { 'puppetlabs':
        key        => '4BD6EC30',
        key_server => 'pgp.mit.edu',
      }

      apt::key { 'jenkins':
        key        => 'D50582E6',
        key_source => 'http://pkg.jenkins-ci.org/debian/jenkins-ci.org.key',
      }
      EOS

      puppet_apply(pp) do |r|
        r.exit_code.should_not == 1
      end
    end

    describe 'keys should exist' do
      it 'finds puppetlabs key' do
        shell('apt-key list | grep 4BD6EC30') do |r|
          r.exit_code.should be_zero
        end
      end
      it 'finds jenkins key' do
        shell('apt-key list | grep D50582E6') do |r|
          r.exit_code.should be_zero
        end
      end
    end
  end

  context 'reset' do
    it 'clean up keys' do
      shell('apt-key del 4BD6EC30')
      shell('apt-key del D50582E6')
    end
  end

end
