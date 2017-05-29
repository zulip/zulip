# What is provisioning?

This documentation explains what do we mean when we speak about provisioning.

## Background

Server provisioning is a set of actions to prepare a server with appropriate systems, data and
software, and make it ready for network operation. Inside Zulip the first time we want to run our server,
we need to do some provisioning for its proper functioning. This includes running a series of processes that
tunes our system, install appropiate software and populate our database to ensure maximum efficiency.
This process can be done by running inside the zulip directory `./tools/provision.py`.
