Puppet::Type.newtype(:anchor) do
  desc <<-'ENDOFDESC'
  A simple resource type intended to be used as an anchor in a composite class.

  In Puppet 2.6, when a class declares another class, the resources in the
  interior class are not contained by the exterior class. This interacts badly
  with the pattern of composing complex modules from smaller classes, as it
  makes it impossible for end users to specify order relationships between the
  exterior class and other modules.

  The anchor type lets you work around this. By sandwiching any interior
  classes between two no-op resources that _are_ contained by the exterior
  class, you can ensure that all resources in the module are contained.

      class ntp {
        # These classes will have the correct order relationship with each
        # other. However, without anchors, they won't have any order
        # relationship to Class['ntp'].
        class { 'ntp::package': }
        -> class { 'ntp::config': }
        -> class { 'ntp::service': }

        # These two resources "anchor" the composed classes within the ntp
        # class.
        anchor { 'ntp::begin': } -> Class['ntp::package']
        Class['ntp::service']    -> anchor { 'ntp::end': }
      }

  This allows the end user of the ntp module to establish require and before
  relationships with Class['ntp']:

      class { 'ntp': } -> class { 'mcollective': }
      class { 'mcollective': } -> class { 'ntp': }

  ENDOFDESC

  newparam :name do
    desc "The name of the anchor resource."
  end

  def refresh
    # We don't do anything with them, but we need this to
    #   show that we are "refresh aware" and not break the
    #   chain of propagation.
  end
end
