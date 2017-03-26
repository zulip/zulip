Puppet Specific Facts
=====================

Facter is meant to stand alone and apart from Puppet.  However, Facter often
runs inside Puppet and all custom facts included in the stdlib module will
almost always be evaluated in the context of Puppet and Facter working
together.

Still, we don't want to write custom facts that blow up in the users face if
Puppet is not loaded in memory.  This is often the case if the user runs
`facter` without also supplying the `--puppet` flag.

Ah! But Jeff, the custom fact won't be in the `$LOAD_PATH` unless the user
supplies `--facter`! You might say...

Not (always) true I say!  If the user happens to have a CWD of
`<modulepath>/stdlib/lib` then the facts will automatically be evaluated and
blow up.

In any event, it's pretty easy to write a fact that has no value if Puppet is
not loaded.  Simply do it like this:

    Facter.add(:node_vardir) do
      setcode do
        # This will be nil if Puppet is not available.
        Facter::Util::PuppetSettings.with_puppet do
          Puppet[:vardir]
        end
      end
    end

The `Facter::Util::PuppetSettings.with_puppet` method accepts a block and
yields to it only if the Puppet library is loaded.  If the Puppet library is
not loaded, then the method silently returns `nil` which Facter interprets as
an undefined fact value.  The net effect is that the fact won't be set.
