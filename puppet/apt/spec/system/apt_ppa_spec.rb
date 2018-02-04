require 'spec_helper_system'

describe 'apt::ppa' do

  context 'reset' do
    it 'removes ppa' do
      shell('rm /etc/apt/sources.list.d/drizzle-developers-ppa*')
      shell('rm /etc/apt/sources.list.d/raravena80-collectd5-*')
    end
  end

  context 'adding a ppa that doesnt exist' do
    it 'should work with no errors' do
      pp = <<-EOS
      include '::apt'
      apt::ppa { 'ppa:drizzle-developers/ppa': }
      EOS

      puppet_apply(pp) do |r|
        r.exit_code.should_not == 1
      end
    end

    describe 'contains the source file' do
      it 'contains a drizzle ppa source' do
        shell('ls /etc/apt/sources.list.d/drizzle-developers-ppa-*.list') do |r|
          r.exit_code.should be_zero
        end
      end
    end
  end

  context 'readding a removed ppa.' do
    it 'setup' do
      shell('add-apt-repository -y ppa:raravena80/collectd5')
      # This leaves a blank file
      shell('add-apt-repository --remove ppa:raravena80/collectd5')
    end

    it 'should readd it successfully' do
      pp = <<-EOS
      include '::apt'
      apt::ppa { 'ppa:raravena80/collectd5': }
      EOS

      puppet_apply(pp) do |r|
        r.exit_code.should_not == 1
      end
    end
  end

  context 'reset' do
    it 'removes added ppas' do
      shell('rm /etc/apt/sources.list.d/drizzle-developers-ppa*')
      shell('rm /etc/apt/sources.list.d/raravena80-collectd5-*')
    end
  end

end
