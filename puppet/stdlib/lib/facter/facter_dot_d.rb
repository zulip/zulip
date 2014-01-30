# A Facter plugin that loads facts from /etc/facter/facts.d
# and /etc/puppetlabs/facter/facts.d.
#
# Facts can be in the form of JSON, YAML or Text files
# and any executable that returns key=value pairs.
#
# In the case of scripts you can also create a file that
# contains a cache TTL.  For foo.sh store the ttl as just
# a number in foo.sh.ttl
#
# The cache is stored in /tmp/facts_cache.yaml as a mode
# 600 file and will have the end result of not calling your
# fact scripts more often than is needed

class Facter::Util::DotD
  require 'yaml'

  def initialize(dir="/etc/facts.d", cache_file="/tmp/facts_cache.yml")
    @dir = dir
    @cache_file = cache_file
    @cache = nil
    @types = {".txt" => :txt, ".json" => :json, ".yaml" => :yaml}
  end

  def entries
    Dir.entries(@dir).reject{|f| f =~ /^\.|\.ttl$/}.sort.map {|f| File.join(@dir, f) }
  rescue
    []
  end

  def fact_type(file)
    extension = File.extname(file)

    type = @types[extension] || :unknown

    type = :script if type == :unknown && File.executable?(file)

    return type
  end

  def txt_parser(file)
    File.readlines(file).each do |line|
      if line =~ /^(.+)=(.+)$/
        var = $1; val = $2

        Facter.add(var) do
          setcode { val }
        end
      end
    end
  rescue Exception => e
    Facter.warn("Failed to handle #{file} as text facts: #{e.class}: #{e}")
  end

  def json_parser(file)
    begin
      require 'json'
    rescue LoadError
      retry if require 'rubygems'
      raise
    end

    JSON.load(File.read(file)).each_pair do |f, v|
      Facter.add(f) do
        setcode { v }
      end
    end
  rescue Exception => e
    Facter.warn("Failed to handle #{file} as json facts: #{e.class}: #{e}")
  end

  def yaml_parser(file)
    require 'yaml'

    YAML.load_file(file).each_pair do |f, v|
      Facter.add(f) do
        setcode { v }
      end
    end
  rescue Exception => e
    Facter.warn("Failed to handle #{file} as yaml facts: #{e.class}: #{e}")
  end

  def script_parser(file)
    result = cache_lookup(file)
    ttl = cache_time(file)

    unless result
      result = Facter::Util::Resolution.exec(file)

      if ttl > 0
        Facter.debug("Updating cache for #{file}")
        cache_store(file, result)
        cache_save!
      end
    else
      Facter.debug("Using cached data for #{file}")
    end

    result.split("\n").each do |line|
      if line =~ /^(.+)=(.+)$/
        var = $1; val = $2

        Facter.add(var) do
          setcode { val }
        end
      end
    end
  rescue Exception => e
    Facter.warn("Failed to handle #{file} as script facts: #{e.class}: #{e}")
    Facter.debug(e.backtrace.join("\n\t"))
  end

  def cache_save!
    cache = load_cache
    File.open(@cache_file, "w", 0600) {|f| f.write(YAML.dump(cache)) }
  rescue
  end

  def cache_store(file, data)
    load_cache

    @cache[file] = {:data => data, :stored => Time.now.to_i}
  rescue
  end

  def cache_lookup(file)
    cache = load_cache

    return nil if cache.empty?

    ttl = cache_time(file)

    if cache[file]
      now = Time.now.to_i

      return cache[file][:data] if ttl == -1
      return cache[file][:data] if (now - cache[file][:stored]) <= ttl
      return nil
    else
      return nil
    end
  rescue
    return nil
  end

  def cache_time(file)
    meta = file + ".ttl"

    return File.read(meta).chomp.to_i
  rescue
    return 0
  end

  def load_cache
    unless @cache
      if File.exist?(@cache_file)
        @cache = YAML.load_file(@cache_file)
      else
        @cache = {}
      end
    end

    return @cache
  rescue
    @cache = {}
    return @cache
  end

  def create
    entries.each do |fact|
      type = fact_type(fact)
      parser = "#{type}_parser"

      if respond_to?("#{type}_parser")
        Facter.debug("Parsing #{fact} using #{parser}")

        send(parser, fact)
      end
    end
  end
end


mdata = Facter.version.match(/(\d+)\.(\d+)\.(\d+)/)
if mdata
  (major, minor, patch) = mdata.captures.map { |v| v.to_i }
  if major < 2
    # Facter 1.7 introduced external facts support directly
    unless major == 1 and minor > 6
      Facter::Util::DotD.new("/etc/facter/facts.d").create
      Facter::Util::DotD.new("/etc/puppetlabs/facter/facts.d").create

      # Windows has a different configuration directory that defaults to a vendor
      # specific sub directory of the %COMMON_APPDATA% directory.
      if Dir.const_defined? 'COMMON_APPDATA' then
        windows_facts_dot_d = File.join(Dir::COMMON_APPDATA, 'PuppetLabs', 'facter', 'facts.d')
        Facter::Util::DotD.new(windows_facts_dot_d).create
      end
    end
  end
end
