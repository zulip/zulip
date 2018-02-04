ENV['FOG_MOCK'] ||= 'true'
ENV['AUTOTEST'] = 'true'
ENV['WATCHR']   = '1'

system 'clear'

def growl(message)
  growlnotify = `which growlnotify`.chomp
  title = "Watchr Test Results"
  image = case message
  when /(\d+)\s+?(failure|error)/i
    ($1.to_i == 0) ? "~/.watchr_images/passed.png" : "~/.watchr_images/failed.png"
  else
    '~/.watchr_images/unknown.png'
  end
  options = "-w -n Watchr --image '#{File.expand_path(image)}' -m '#{message}' '#{title}'"
  system %(#{growlnotify} #{options} &)
end

def run(cmd)
  puts(cmd)
  `#{cmd}`
end

def run_spec_test(file)
  if File.exist? file
    result = run "rspec --format p --color #{file}"
    growl result.split("\n").last
    puts result
  else
    puts "FIXME: No test #{file} [#{Time.now}]"
  end
end

def filter_rspec(data)
  data.split("\n").find_all do |l|
    l =~ /^(\d+)\s+exampl\w+.*?(\d+).*?failur\w+.*?(\d+).*?pending/
  end.join("\n")
end

def run_all_tests
  system('clear')
  files = Dir.glob("spec/**/*_spec.rb").join(" ")
  result = run "rspec #{files}"
  growl_results = filter_rspec result
  growl growl_results
  puts result
  puts "GROWL: #{growl_results}"
end

# Ctrl-\
Signal.trap 'QUIT' do
  puts " --- Running all tests ---\n\n"
  run_all_tests
end

@interrupted = false

# Ctrl-C
Signal.trap 'INT' do
  if @interrupted then
    @wants_to_quit = true
    abort("\n")
  else
    puts "Interrupt a second time to quit"
    @interrupted = true
    Kernel.sleep 1.5
    # raise Interrupt, nil # let the run loop catch it
    run_suite
  end
end

def file2spec(file)
  result = file.sub('lib/puppet/', 'spec/unit/puppet/').gsub(/\.rb$/, '_spec.rb')
  result = file.sub('lib/facter/', 'spec/unit/facter/').gsub(/\.rb$/, '_spec.rb')
end


watch( 'spec/.*_spec\.rb' ) do |md|
  #run_spec_test(md[0])
  run_all_tests
end
watch( 'lib/.*\.rb' ) do |md|
  # run_spec_test(file2spec(md[0]))
  run_all_tests
end
