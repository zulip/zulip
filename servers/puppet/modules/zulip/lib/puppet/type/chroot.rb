Puppet::Type.newtype(:chroot) do
    ensurable
    newparam(:release) do
       desc "The name of the release"
       isnamevar
    end
    newparam(:distro) do
       desc "The name of the Linux distribution (Debian, Ubuntu)"
    end
end

Puppet::Type.type(:chroot).provide(:chroot) do
  def exists?
    File.exists?("/var/lib/schroot/chroots/" + resource[:release] + "-amd64")
  end

  def create
    if @resource[:distro] == "ubuntu"
        mirror = "http://mirror.cc.columbia.edu/pub/linux/ubuntu/archive/"
    else
        mirror = "http://mirror.cc.columbia.edu/debian"
    end
    ["amd64", "i386"].each { |x|
        system("mk-sbuild #{@resource[:release]} --arch=#{x} --debootstrap-mirror=#{mirror} --distro=#{@resource[:distro]}")
    }
  end

  def destroy
    system("rm -rf /var/lib/schroot/chroots/#{@resource[:release]}-*")
  end
end
