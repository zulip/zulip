Facter.add(:io_uring_available) do
  confine :kernel => 'Linux'
  setcode do
    # Syscall 425 is io_uring_setup
    # https://www.chromium.org/chromium-os/developer-library/reference/linux-constants/syscalls/#x86_64_425
    # https://manpages.debian.org/trixie/liburing-dev/io_uring_setup.2.en.html
    #
    # We get ENOSYS if the kernel doesn't have the syscall, or EPERM
    # if it's disabled or restricted via seccomp (i.e. in Docker)
    result = Facter::Core::Execution.execute(
      "perl -MErrno=EPERM,ENOSYS -e 'syscall(425); exit((\$! != EPERM and \$! != ENOSYS) ? 0 : 1)'",
      :on_fail => :failed
    )
    result != :failed && $?.success?
  end
end
