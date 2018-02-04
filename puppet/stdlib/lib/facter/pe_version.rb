# Fact: is_pe, pe_version, pe_major_version, pe_minor_version, pe_patch_version
#
# Purpose: Return various facts about the PE state of the system
#
# Resolution: Uses a regex match against puppetversion to determine whether the
#   machine has Puppet Enterprise installed, and what version (overall, major,
#   minor, patch) is installed.
#
# Caveats:
#
Facter.add("pe_version") do
  setcode do
    pe_ver = Facter.value("puppetversion").match(/Puppet Enterprise (\d+\.\d+\.\d+)/)
    pe_ver[1] if pe_ver
  end
end

Facter.add("is_pe") do
  setcode do
    if Facter.value(:pe_version).to_s.empty? then
      false
    else
      true
    end
  end
end

Facter.add("pe_major_version") do
  confine :is_pe => true
  setcode do
    if pe_version = Facter.value(:pe_version)
      pe_version.to_s.split('.')[0]
    end
  end
end

Facter.add("pe_minor_version") do
  confine :is_pe => true
  setcode do
    if pe_version = Facter.value(:pe_version)
      pe_version.to_s.split('.')[1]
    end
  end
end

Facter.add("pe_patch_version") do
  confine :is_pe => true
  setcode do
    if pe_version = Facter.value(:pe_version)
      pe_version.to_s.split('.')[2]
    end
  end
end
