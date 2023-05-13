module Puppet::Parser::Functions
  newfunction(:zulipsecret, :type => :rvalue) do |args|
    default = args.pop
    output = `/usr/bin/crudini --get /etc/zulip/zulip-secrets.conf #{args.shelljoin} 2>&1`; result = $?.success?
    if result
      output.strip()
    else
      default
    end
  end
end
