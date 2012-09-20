output = %x{apt-get -v 2>&1}

if $?.exitstatus and output.match(/apt (\d+\.\d+\.\d+).*/)

  Facter.add("apt_version") do
    setcode do
      $1
    end
  end
end
