Facter.add(:zulip_version) do
  setcode do
    Dir.chdir("/home/zulip/deployments/current") do
      output = `python3 -c 'import version; print(version.ZULIP_VERSION_WITHOUT_COMMIT)' 2>&1`
      if not $?.success?
        Facter.debug("zulip_version error: #{output}")
        nil
      else
        output.strip
      end
    end
  end
end
