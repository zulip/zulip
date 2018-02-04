# Contributing to this module #

 * Work in a topic branch
 * Submit a github pull request
 * Address any comments / feeback
 * Merge into master using --no-ff

# Releasing this module #

 * This module adheres to http://semver.org/
 * Look for API breaking changes using git diff vX.Y.Z..master
   * If no API breaking changes, the minor version may be bumped.
   * If there are API breaking changes, the major version must be bumped.
   * If there are only small minor changes, the patch version may be bumped.
 * Update the CHANGELOG
 * Update the Modulefile
 * Commit these changes with a message along the lines of "Update CHANGELOG and
   Modulefile for release"
 * Create an annotated tag with git tag -a vX.Y.Z -m 'version X.Y.Z' (NOTE the
   leading v as per semver.org)
 * Push the tag with git push origin --tags
 * Build a new package with puppet-module or the rake build task if it exists
 * Publish the new package to the forge
 * Bonus points for an announcement to puppet-users.
