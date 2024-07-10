If you ever want to recreate your development environment again from
scratch (e.g., to test a change you've made to the provisioning
process, or because you think something is broken), you can do so
using `vagrant destroy` and then `vagrant up`. This will usually be
much faster than the original `vagrant up` since the base image is
already cached on your machine (it takes about 5 minutes to run with a
fast Internet connection).

Any additional programs (e.g., Zsh, emacs, etc.) or configuration that
you may have installed in the development environment will be lost
when you recreate it. To address this, you can create a script called
`tools/custom_provision` in your Zulip Git checkout; and place any
extra setup commands there. Vagrant will run `tools/custom_provision`
every time you run `vagrant provision` (or create a Vagrant guest via
`vagrant up`).
