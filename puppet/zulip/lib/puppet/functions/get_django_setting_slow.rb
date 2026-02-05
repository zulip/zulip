require "shellwords"

# Note that this is very slow (~350ms) and may get values which will
# rapidly go out of date, since settings are changed much more
# frequently than deploys -- in addition to potentially just not
# working if we're not on the application server.  We should generally
# avoid using this if at all possible.

Puppet::Functions.create_function(:get_django_setting_slow) do
  def get_django_setting_slow(name)
    if File.exist?("/etc/zulip/settings.py")
      if Dir.exist?("/home/zulip/deployments/current")
        deploy_dir = "current"
      else
        # First puppet runs during install don't have a "current" yet, only a "next"
        deploy_dir = "next"
      end
      output = `/home/zulip/deployments/#{deploy_dir}/scripts/get-django-setting #{name.shellescape} 2>&1`
      if $?.success?
        output.strip
      else
        nil
      end
    else
      nil
    end
  end
end
