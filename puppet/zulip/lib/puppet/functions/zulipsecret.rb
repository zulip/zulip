require "shellwords"

Puppet::Functions.create_function(:zulipsecret) do
  def zulipsecret(section, key, default)
    output = `/usr/bin/crudini --get -- /etc/zulip/zulip-secrets.conf #{[section, key].shelljoin} 2>&1`; result = $?.success?
    if result
      output.strip()
    else
      default
    end
  end
end
