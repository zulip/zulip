### Install the bridge software

1. Clone the Zulip API repository, and install its dependencies:

    ```
    git clone https://github.com/zulip/python-zulip-api.git
    cd python-zulip-api
    python3 ./tools/provision
    ```

1. Activate the virtualenv by running the `source` command printed
   at the end of the `provision` output.

1. To install the Matrix bridge software in your virtualenv, run:

    ```
    pip install -r zulip/integrations/matrix/requirements.txt
    ```

This will create a new Python virtual environment, with all the
dependences for this bridge installed.  You'll want to run the bridge
service inside this virtualenv.
