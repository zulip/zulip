require 'spec_helper'
describe 'apt::force', :type => :define do
  let :title do
    'my_package'
  end

  let :default_params do
    {
      :release => 'testing',
      :version => false
    }
  end

  [{},
   {
      :release  => 'stable',
      :version  => '1'
    }
  ].each do |param_set|
    describe "when #{param_set == {} ? "using default" : "specifying"} define parameters" do
      let :param_hash do
        default_params.merge(param_set)
      end

      let :params do
        param_set
      end

      let :unless_query do
        base_command = "/usr/bin/dpkg -s #{title} | grep -q "
        base_command + (params[:version] ? "'Version: #{params[:version]}'" : "'Status: install'")
      end

      let :exec_title do
        base_exec = "/usr/bin/apt-get -y -t #{param_hash[:release]} install #{title}"
        base_exec + (params[:version] ? "=#{params[:version]}" : "")
      end
      it { should contain_exec(exec_title).with_unless(unless_query) }
    end
  end
end
