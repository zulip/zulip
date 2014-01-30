require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_absolute_path) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  # The subject of these examples is the method itself.
  subject do
    # This makes sure the function is loaded within each test
    function_name = Puppet::Parser::Functions.function(:validate_absolute_path)
    scope.method(function_name)
  end

  describe "Valid Paths" do
    def self.valid_paths
      %w{
        C:/
        C:\\
        C:\\WINDOWS\\System32
        C:/windows/system32
        X:/foo/bar
        X:\\foo\\bar
        /var/tmp
        /var/lib/puppet
        /var/opt/../lib/puppet
      }
    end

    context "Without Puppet::Util.absolute_path? (e.g. Puppet <= 2.6)" do
      before :each do
        # The intent here is to mock Puppet to behave like Puppet 2.6 does.
        # Puppet 2.6 does not have the absolute_path? method.  This is only a
        # convenience test, stdlib should be run with the Puppet 2.6.x in the
        # $LOAD_PATH in addition to 2.7.x and master.
        Puppet::Util.expects(:respond_to?).with(:absolute_path?).returns(false)
      end
      valid_paths.each do |path|
        it "validate_absolute_path(#{path.inspect}) should not fail" do
          expect { subject.call [path] }.not_to raise_error Puppet::ParseError
        end
      end
    end

    context "Puppet without mocking" do
      valid_paths.each do |path|
        it "validate_absolute_path(#{path.inspect}) should not fail" do
          expect { subject.call [path] }.not_to raise_error Puppet::ParseError
        end
      end
    end
  end

  describe 'Invalid paths' do
    context 'Garbage inputs' do
      [
        nil,
        [ nil ],
        { 'foo' => 'bar' },
        { },
        '',
      ].each do |path|
        it "validate_absolute_path(#{path.inspect}) should fail" do
          expect { subject.call [path] }.to raise_error Puppet::ParseError
        end
      end
    end

    context 'Relative paths' do
      %w{
        relative1
        .
        ..
        ./foo
        ../foo
        etc/puppetlabs/puppet
        opt/puppet/bin
      }.each do |path|
        it "validate_absolute_path(#{path.inspect}) should fail" do
          expect { subject.call [path] }.to raise_error Puppet::ParseError
        end
      end
    end
  end
end
