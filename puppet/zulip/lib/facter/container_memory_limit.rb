Facter.add(:container_memory_limit_mb) do
  confine kernel: 'Linux'

  setcode do
    begin
      memory_limit_mb = nil

      # Check for cgroup v2
      if File.exist?('/sys/fs/cgroup/memory.max')
        val = File.read('/sys/fs/cgroup/memory.max').strip
        memory_limit_mb = val.to_i / 1024 / 1024 unless val == 'max'

      # Fallback to cgroup v1
      elsif File.exist?('/sys/fs/cgroup/memory/memory.limit_in_bytes')
        val = File.read('/sys/fs/cgroup/memory/memory.limit_in_bytes').strip.to_i
        memory_limit_mb = val / 1024 / 1024 if val < 9223372036854771712
      end

      memory_limit_mb
    rescue => e
      Facter.debug("container_memory_limit_mb error: #{e}")
      nil
    end
  end
end
