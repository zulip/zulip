require "open3"

Facter.add(:zulip_version) do
  setcode do
    Dir.chdir(File.expand_path("../../../../", __dir__)) do
      output, stderr, status = Open3.capture3(
        "python3", "-c", "import version; print(version.ZULIP_VERSION_WITHOUT_COMMIT)"
      )
      if not status.success?
        Facter.debug("zulip_version error: #{stderr}")
        nil
      else
        output.strip
      end
    end
  end
end
