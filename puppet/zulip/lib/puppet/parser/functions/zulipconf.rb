module Puppet::Parser::Functions
  newfunction(:zulipconf, :type => :rvalue) do |args|
    default = args.pop
    joined = args.join(" ")
    zulip_conf_path = lookupvar('zulip_conf_path')
    output = `/usr/bin/crudini --get #{zulip_conf_path} #{joined} 2>&1`; result=$?.success?
    if result
      output.strip()
    else
      default
    end
  end
end
