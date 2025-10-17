require "shellwords"

Puppet::Functions.create_function(:get_django_setting) do
  def get_django_setting(name)
    if File.exist?("/etc/zulip/settings.py")
      output = `/home/zulip/deployments/current/scripts/get-django-setting #{name.shellescape} 2>&1`
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
