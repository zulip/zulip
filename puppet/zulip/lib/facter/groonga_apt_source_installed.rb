Facter.add(:groonga_apt_source_installed) do
  confine kernel: 'Linux'

  setcode do
    # scripts/setup/apt-repos/zulip/custom.sh installs this package
    # on the platforms where packages.groonga.org has PGroonga packages.
    File.exist?('/usr/share/doc/groonga-apt-source/copyright')
  end
end
