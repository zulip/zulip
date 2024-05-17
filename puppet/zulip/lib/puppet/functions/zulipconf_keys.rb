require "shellwords"

Puppet::Functions.create_function(:zulipconf_keys) do
  def zulipconf_keys(section)
    zulip_conf_path = Facter.value("zulip_conf_path")
    output = `/usr/bin/crudini --get -- #{[zulip_conf_path, section].shelljoin} 2>&1`; result = $?.success?
    if result
      return output.lines.map { |l| l.strip }
    else
      return []
    end
  end
end
