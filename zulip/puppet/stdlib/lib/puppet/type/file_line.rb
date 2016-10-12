Puppet::Type.newtype(:file_line) do

  desc <<-EOT
    Ensures that a given line is contained within a file.  The implementation
    matches the full line, including whitespace at the beginning and end.  If
    the line is not contained in the given file, Puppet will add the line to
    ensure the desired state.  Multiple resources may be declared to manage
    multiple lines in the same file.

    Example:

        file_line { 'sudo_rule':
          path => '/etc/sudoers',
          line => '%sudo ALL=(ALL) ALL',
        }
        file_line { 'sudo_rule_nopw':
          path => '/etc/sudoers',
          line => '%sudonopw ALL=(ALL) NOPASSWD: ALL',
        }

    In this example, Puppet will ensure both of the specified lines are
    contained in the file /etc/sudoers.

  EOT

  ensurable do
    defaultvalues
    defaultto :present
  end

  newparam(:name, :namevar => true) do
    desc 'An arbitrary name used as the identity of the resource.'
  end

  newparam(:match) do
    desc 'An optional regular expression to run against existing lines in the file;\n' +
        'if a match is found, we replace that line rather than adding a new line.'
  end

  newparam(:line) do
    desc 'The line to be appended to the file located by the path parameter.'
  end

  newparam(:path) do
    desc 'The file Puppet will ensure contains the line specified by the line parameter.'
    validate do |value|
      unless (Puppet.features.posix? and value =~ /^\//) or (Puppet.features.microsoft_windows? and (value =~ /^.:\// or value =~ /^\/\/[^\/]+\/[^\/]+/))
        raise(Puppet::Error, "File paths must be fully qualified, not '#{value}'")
      end
    end
  end

  # Autorequire the file resource if it's being managed
  autorequire(:file) do
    self[:path]
  end

  validate do
    unless self[:line] and self[:path]
      raise(Puppet::Error, "Both line and path are required attributes")
    end

    if (self[:match])
      unless Regexp.new(self[:match]).match(self[:line])
        raise(Puppet::Error, "When providing a 'match' parameter, the value must be a regex that matches against the value of your 'line' parameter")
      end
    end

  end
end
