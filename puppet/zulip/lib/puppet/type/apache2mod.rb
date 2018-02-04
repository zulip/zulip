Puppet::Type.newtype(:apache2mod) do
    ensurable
    newparam(:name) do
       desc "The name of the module to enable"
       isnamevar
    end
end

Puppet::Type.type(:apache2mod).provide(:apache2mod) do
  def exists?
    File.exists?("/etc/apache2/mods-enabled/" + resource[:name] + ".load")
  end

  def create
    system("a2enmod #{@resource[:name]}")
  end

  def destroy
    system("a2dismod #{@resource[:name]}")
  end
end
