<?php
// vim:sw=2:softtabstop=2:textwidth=80
//
// This program is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by the Free
// Software Foundation, either version 2 of the License, or (at your option)
// any later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
// FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
// more details.
//
// You should have received a copy of the GNU General Public License along with
// this program.  If not, see <http://www.gnu.org/licenses/>.
//
// Copyright 2006 Otheus Shelling
// Copyright 2007 Rusty Burchfield
// Copyright 2009 James Kinsman
// Copyright 2010 Daniel Thomas
// Copyright 2010 Ian Ward Comfort
//
// In 2009, the copyright holders determined that the original publishing of this code
// under GPLv3 was legally and logistically in error, and re-licensed it under GPLv2.
//
// See http://www.mediawiki.org/wiki/Extension:AutomaticREMOTE_USER
//
// Adapted by Rusty to be compatible with version 1.9 of MediaWiki
// Optional settings from Emmanuel Dreyfus
// Adapted by VibroAxe (James Kinsman) to be compatible with version 1.16 of MediaWiki
// Adapted by VibroAxe (James Kinsman) to allow domain substitution for Integrated Windows Authentication
// Adapted by drt24 (Daniel Thomas) to add the optional $wgAuthRemoteuserMailDomain and remove hardcoding
//   of permissions for anonymous users.
// Adapted by Ian Ward Comfort to detect mismatches between the session user and REMOTE_USER
//
// Add these lines to your LocalSettings.php
//
// // Don't let anonymous people do things...
// $wgGroupPermissions['*']['createaccount']   = false;
// $wgGroupPermissions['*']['read']            = false;
// $wgGroupPermissions['*']['edit']            = false;
//
// /* This is required for Auth_remoteuser operation
// require_once('extensions/Auth_remoteuser.php');
// $wgAuth = new Auth_remoteuser();
//
// The constructor of Auth_remoteuser registers a hook to do the automatic
// login.  Storing the Auth_remoteuser object in $wgAuth tells mediawiki to use
// that object as the AuthPlugin.  This way the login attempts by the hook will
// be handled by us.
//
// You probably want to edit the initUser function to set the users real name
// and email address properly for your configuration.

// Extension credits that show up on Special:Version
$wgExtensionCredits['other'][] = array(
		'name' => 'AutomaticREMOTE USER',
		'version' => '1.1.4',
		'author' => array( 'Otheus Shelling', 'Rusty Burchfield', 'James Kinsman', 'Daniel Thomas', 'Ian Ward Comfort' ),
		'url' => 'https://www.mediawiki.org/wiki/Extension:AutomaticREMOTE_USER',
		'description' => 'Automatically logs users using the REMOTE_USER environment variable.',
);

// We must allow zero length passwords. This extension does not work in MW 1.16 without this.
$wgMinimalPasswordLength = 0;

$wgAuthRemoteuserAuthz = true;
$wgAuthRemoteuserDomain = null;

/* User's name */
$wgAuthRemoteuserName = isset( $_SERVER["AUTHENTICATE_CN"] )
	? $_SERVER["AUTHENTICATE_CN"]
	: '';

/* User's Mail */
$wgAuthRemoteuserMail = isset( $_SERVER["AUTHENTICATE_MAIL"] )
	? $_SERVER["AUTHENTICATE_MAIL"]
	: '';
$wgAuthRemoteuserNotify = false; /* Do not send mail notifications */
$wgAuthRemoteuserDomain = "NETBIOSDOMAIN"; /* Remove NETBIOSDOMAIN\ from the beginning or @NETBIOSDOMAIN at the end of a IWA username */
/* User's mail domain to append to the user name to make their email address */
$wgAuthRemoteuserMailDomain = "example.com";

$wgExtensionFunctions[] = 'Auth_remote_user_hook';

/**
 * This hook is registered by the Auth_remoteuser constructor.  It will be
 * called on every page load.  It serves the function of automatically logging
 * in the user.  The Auth_remoteuser class is an AuthPlugin and handles the
 * actual authentication, user creation, etc.
 *
 * Details:
 * 1. Check to see if the user has a session and is not anonymous.  If this is
 *    true, check whether REMOTE_USER matches the session user.  If so, we can
 *    just return; otherwise we must logout the session user and login as the
 *    REMOTE_USER.
 * 2. If the user doesn't have a session, we create a login form with our own
 *    fake request and ask the form to authenticate the user.  If the user does
 *    not exist authenticateUserData will attempt to create one.  The login form
 *    uses our Auth_remoteuser class as an AuthPlugin.
 *
 * Note: If cookies are disabled, an infinite loop /might/ occur?
 */
function Auth_remote_user_hook() {
	global $wgUser, $wgRequest, $wgAuthRemoteuserDomain, $wgAuth;

	// For a few special pages, don't do anything.
	$title = $wgRequest->getVal( 'title' );
	if ( ( $title == Title::makeName( NS_SPECIAL, 'UserLogout' ) ) ||
		( $title == Title::makeName( NS_SPECIAL, 'UserLogin' ) ) ) {
		return;
	}

	// Process the username if required
	if ( !isset( $_SERVER['REMOTE_USER'] ) ) {
		return;
	}
	if ( isset( $wgAuthRemoteuserDomain ) && strlen( $wgAuthRemoteuserDomain ) ) {
		$username = str_replace( "$wgAuthRemoteuserDomain\\", "", $_SERVER['REMOTE_USER'] );
		$username = str_replace( "@$wgAuthRemoteuserDomain", "", $username );
	} else {
		$username = $_SERVER['REMOTE_USER'];
	}

	// Check for valid session
	$user = User::newFromSession();
	if ( !$user->isAnon() ) {
		if ( $user->getName() == $wgAuth->getCanonicalName( $username ) ) {
			return;            // Correct user is already logged in.
		} else {
			$user->doLogout(); // Logout mismatched user.
		}
	}

	// Copied from includes/SpecialUserlogin.php
	if ( !isset( $wgCommandLineMode ) && !isset( $_COOKIE[session_name()] ) ) {
		wfSetupSession();
	}

	// If the login form returns NEED_TOKEN try once more with the right token
	$trycount = 0;
	$token = '';
	$errormessage = '';
	do {
		$tryagain = false;
		// Submit a fake login form to authenticate the user.
		$params = new FauxRequest( array(
			'wpName' => $username,
			'wpPassword' => '',
			'wpDomain' => '',
			'wpLoginToken' => $token,
			'wpRemember' => ''
			) );

		// Authenticate user data will automatically create new users.
		$loginForm = new LoginForm( $params );
		$result = $loginForm->authenticateUserData();
		switch ( $result ) {
			case LoginForm :: SUCCESS :
				$wgUser->setOption( 'rememberpassword', 1 );
				$wgUser->setCookies();
				break;
			case LoginForm :: NEED_TOKEN:
				$token = $loginForm->getLoginToken();
				$tryagain = ( $trycount == 0 );
				break;
			case LoginForm :: WRONG_TOKEN:
				$errormessage = 'WrongToken';
				break;
			case LoginForm :: NO_NAME :
				$errormessage = 'NoName';
				break;
			case LoginForm :: ILLEGAL :
				$errormessage = 'Illegal';
				break;
			case LoginForm :: WRONG_PLUGIN_PASS :
				$errormessage = 'WrongPluginPass';
				break;
			case LoginForm :: NOT_EXISTS :
				$errormessage = 'NotExists';
				break;
			case LoginForm :: WRONG_PASS :
				$errormessage = 'WrongPass';
				break;
			case LoginForm :: EMPTY_PASS :
				$errormessage = 'EmptyPass';
				break;
			default:
				$errormessage = 'Unknown';
				break;
		}

		if ( $result != LoginForm::SUCCESS && $result != LoginForm::NEED_TOKEN ) {
			error_log( 'Unexpected REMOTE_USER authentication failure. Login Error was:' . $errormessage );
		}
		$trycount++;
	} while ( $tryagain );

	return;
}

class Auth_remoteuser extends AuthPlugin {
	/**
	 * Disallow password change.
	 *
	 * @return bool
	 */
	function allowPasswordChange() {
		return false;
	}

	/**
	 * This should not be called because we do not allow password change.  Always
	 * fail by returning false.
	 *
	 * @param $user User object.
	 * @param $password String: password.
	 * @return bool
	 * @public
	 */
	function setPassword( $user, $password ) {
		return false;
	}

	/**
	 * We don't support this but we have to return true for preferences to save.
	 *
	 * @param $user User object.
	 * @return bool
	 * @public
	 */
	function updateExternalDB( $user ) {
		return true;
	}

	/**
	 * We can't create external accounts so return false.
	 *
	 * @return bool
	 * @public
	 */
	function canCreateAccounts() {
		return false;
	}

	/**
	 * We don't support adding users to whatever service provides REMOTE_USER, so
	 * fail by always returning false.
	 *
	 * @param User $user
	 * @param string $password
	 * @return bool
	 * @public
	 */
	function addUser( $user, $password ) {
		return false;
	}

	/**
	 * Pretend all users exist.  This is checked by authenticateUserData to
	 * determine if a user exists in our 'db'.  By returning true we tell it that
	 * it can create a local wiki user automatically.
	 *
	 * @param $username String: username.
	 * @return bool
	 * @public
	 */
	function userExists( $username ) {
		return true;
	}

	/**
	 * Check whether the given name matches REMOTE_USER.
	 * The name will be normalized to MediaWiki's requirements, so
	 * lower it and the REMOTE_USER before checking.
	 *
	 * @param $username String: username.
	 * @param $password String: user password.
	 * @return bool
	 * @public
	 */
	function authenticate( $username, $password ) {
		global $wgAuthRemoteuserAuthz, $wgAuthRemoteuserDomain;

		if ( isset( $wgAuthRemoteuserAuthz ) && !$wgAuthRemoteuserAuthz ) {
			return false;
		}

		if ( !isset( $_SERVER['REMOTE_USER'] ) ) {
			$_SERVER['REMOTE_USER'] = "";
		}

		if ( isset( $wgAuthRemoteuserDomain ) && strlen( $wgAuthRemoteuserDomain ) > 0 ) {
			$usertest = str_replace( "$wgAuthRemoteuserDomain\\", "", $_SERVER['REMOTE_USER'] );
			$usertest = str_replace( "@$wgAuthRemoteuserDomain", "", $usertest );
		} else {
			$usertest = $_SERVER['REMOTE_USER'];
		}

		return ( strtolower( $username ) == strtolower( $usertest ) );
	}

	/**
	 * Check to see if the specific domain is a valid domain.
	 *
	 * @param $domain String: authentication domain.
	 * @return bool
	 * @public
	 */
	function validDomain( $domain ) {
		return true;
	}

	/**
	 * When a user logs in, optionally fill in preferences and such.
	 * For instance, you might pull the email address or real name from the
	 * external user database.
	 *
	 * The User object is passed by reference so it can be modified; don't
	 * forget the & on your function declaration.
	 *
	 * @param User $user
	 * @public
	 */
	function updateUser( &$user ) {
		// We only set this stuff when accounts are created.
		return true;
	}

	/**
	 * Return true because the wiki should create a new local account
	 * automatically when asked to login a user who doesn't exist locally but
	 * does in the external auth database.
	 *
	 * @return bool
	 * @public
	 */
	function autoCreate() {
		return true;
	}

	/**
	 * Return true to prevent logins that don't authenticate here from being
	 * checked against the local database's password fields.
	 *
	 * @return bool
	 * @public
	 */
	function strict() {
		return true;
	}

	/**
	 * When creating a user account, optionally fill in preferences and such.
	 * For instance, you might pull the email address or real name from the
	 * external user database.
	 *
	 * @param $user User object.
	 * @public
	 */
	function initUser( &$user ) {
		global $wgAuthRemoteuserName, $wgAuthRemoteuserMail, $wgAuthRemoteuserMailDomain,
			$wgAuthRemoteuserNotify, $wgAuthRemoteuserDomain;

		if ( isset( $wgAuthRemoteuserDomain ) && strlen( $wgAuthRemoteuserDomain ) ) {
			$username = str_replace( "$wgAuthRemoteuserDomain\\", "", $_SERVER['REMOTE_USER'] );
			$username = str_replace( "@$wgAuthRemoteuserDomain", "", $username );
		} else {
			$username = $_SERVER['REMOTE_USER'];
		}

		if ( isset( $wgAuthRemoteuserName ) ) {
			$user->setRealName( $wgAuthRemoteuserName );
		} else {
			$user->setRealName( '' );
		}

		if ( isset( $wgAuthRemoteuserMail ) ) {
			$user->setEmail( $wgAuthRemoteuserMail );
		} elseif ( isset( $wgAuthRemoteuserMailDomain ) ) {
			$user->setEmail( $username . '@' . $wgAuthRemoteuserMailDomain );
		} else {
			$user->setEmail( $username . "@example.com" );
		}

		$user->mEmailAuthenticated = wfTimestampNow();
		$user->setToken();

		// turn on e-mail notifications
		if ( isset( $wgAuthRemoteuserNotify ) && $wgAuthRemoteuserNotify ) {
			$user->setOption( 'enotifwatchlistpages', 1 );
			$user->setOption( 'enotifusertalkpages', 1 );
			$user->setOption( 'enotifminoredits', 1 );
			$user->setOption( 'enotifrevealaddr', 1 );
		}

		$user->saveSettings();
	}

	/**
	 * Modify options in the login template.  This shouldn't be very important
	 * because no one should really be bothering with the login page.
	 *
	 * @param $template UserLoginTemplate object.
	 * @public
	 */
	function modifyUITemplate( &$template ) {
		// disable the mail new password box
		$template->set( 'useemail', false );
		// disable 'remember me' box
		$template->set( 'remember', false );
		$template->set( 'create', false );
		$template->set( 'domain', false );
		$template->set( 'usedomain', false );
	}

	/**
	 * Normalize user names to the MediaWiki standard to prevent duplicate
	 * accounts.
	 *
	 * @param $username String: username.
	 * @return string
	 * @public
	 */
	function getCanonicalName( $username ) {
		// lowercase the username
		$username = strtolower( $username );
		// uppercase first letter to make MediaWiki happy
		return ucfirst( $username );
	}
}

