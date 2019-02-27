**Easy Image Build System**

This fabric.py project will allow you to create your image without the need to write any Python code.  Simply copy your bash scripts and files into the proper locations and run it against your build droplet following these steps:

1. Add any files you wish to have included in your image to the "files" directory.  Under "files" you can create any directories or files needed and tey will be uploaded to the associated location on your build droplet.  To create the file "/etc/hello_world.txt" on the build system add it as "files/etc/hello_world.txt"  
2. Add any scripts that should be run to install and configure your software before the image is created to the "scripts" directory.  Subdirectories under "scripts" will be ignored.  These scripts will each be uploaded to "/tmp" on your build droplet, given execute permissions and run.  The cleanup process included here will remove these scripts before you snapshot your droplet.
3. packages.txt should be a space-separated list of packages that should be installed via apt-get on your build system.  Include all package names on a single line.

Once you've added your files and created your package list you can perform a test run of your script

`fab build_test -H [BUILD_DROPLET_IP]`

This will install your files and packages and run your scripts but will not perform a cleanup of the build system or power it down.  This can be used for testing during development.

`fab build_image -H [BUILD_DROPLET_IP]`

This task will perform all steps (upload files, run scripts, install packages, clean up build system, power off) to prepare your droplet for snapshot.
