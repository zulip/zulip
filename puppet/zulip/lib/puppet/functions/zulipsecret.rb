require "open3"

Puppet::Functions.create_function(:zulipsecret) do
  def zulipsecret(section, key, default)
    output, _stderr, status = Open3::capture3("/usr/bin/crudini", "--get", "--", "/etc/zulip/zulip-secrets.conf", section, key)
    if status.success?
      output.strip()
    else
      default
    end
  end
end
