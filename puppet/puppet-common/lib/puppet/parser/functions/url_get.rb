# Returns the content at given URL

module Puppet::Parser::Functions
  newfunction(:url_get, :type => :rvalue) do |args|
    require 'open-uri'

    url = args[0]

    begin
      data = open(url, :proxy => nil)
      # Ignore header
      data.readline
      data.readline.chomp
    rescue OpenURI::HTTPError => error
      fail "Fetching URL #{url} failed with status #{error.message}"
    end
  end
end

