# Work around https://bugs.launchpad.net/ubuntu/+source/puppet/+bug/1969939.

require 'fileutils'

def FileUtils.symlink(src, dest, options = {}, **kwargs)
  FileUtils.ln_s(src, dest, **options, **kwargs)
end
