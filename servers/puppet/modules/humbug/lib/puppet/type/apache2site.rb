Puppet::Type.newtype(:apache2site) do
    ensurable
    newparam(:name) do
       desc "The name of the site to enable"
       isnamevar
    end
end

Puppet::Type.type(:apache2site).provide(:apache2site) do
  def exists?
    File.exists?("/etc/apache2/sites-enabled/" + resource[:name])
  end

  def create
    system("a2ensite #{@resource[:name]}")
  end

  def destroy
    system("a2ensite #{@resource[:name]}")
  end
end
