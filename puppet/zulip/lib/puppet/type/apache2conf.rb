Puppet::Type.newtype(:apache2conf) do
  ensurable
  newparam(:name) do
    desc "The name of the conf to enable"
    isnamevar
  end
end

Puppet::Type.type(:apache2conf).provide(:apache2conf) do
  def exists?
    File.exists?("/etc/apache2/conf-enabled/" + resource[:name] + ".conf")
  end

  def create
    system("a2enconf #{@resource[:name]}")
  end

  def destroy
    system("a2disconf #{@resource[:name]}")
  end
end
