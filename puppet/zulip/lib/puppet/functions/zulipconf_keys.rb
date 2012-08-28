require "open3"

Puppet::Functions.create_function(:zulipconf_keys) do
  def zulipconf_keys(section)
    zulip_conf_path = Facter.value("zulip_conf_path")
    output, _stderr, status = Open3.capture3("/usr/bin/crudini", "--get", "--", zulip_conf_path, section)
    if status.success?
      return output.lines.map { |l| l.strip }
    else
      return []
    end
  end
end
