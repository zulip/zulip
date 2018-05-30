### Install the bridge software

You can install the bridge software as follows:

1.  First, clone the Zulip API and install its dependencies:

    ```
    git clone https://github.com/zulip/python-zulip-api.git
    cd python-zulip-api
    python3 ./tools/provision
    ```

1. Next, enter the virtualenv, by running the `source` command printed
   at the end of the `provision` output.

1.  Then, run this to install the Matrix bridge software in your virtualenv.

    ```
    pip install -r zulip/integrations/matrix/requirements.txt
    ```

This will create a new Python virtual environment, with all the
dependences for this bridge installed.  You'll want to run the bridge
service inside this virtualenv.  If you later need to enter the
virtualenv (from e.g. a new shell), you can use the `source` command.
