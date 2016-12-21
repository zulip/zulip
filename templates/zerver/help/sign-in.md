# Signing in
![Zulip login page](/static/images/help/zulip-login.png)

Zulip offers realm administrators the option of enabling multiple methods for users to sign in to their Zulip organization. If your realm administrators have enabled Google or GitHub authentication, you can use the credentials to your Google or GitHub account as an alternative to using your account's email address and password to sign in.

## Signing in with your email address
![Zulip sign in email](/static/images/help/signin-email.png)

You can sign in to your Zulip organization using your email address by following a few simple steps.

1. In the field labeled **Email**, enter the email address that you signed up to Zulip with. Please note that the **Email** field is case-sensitive.

    If you've forgotten which email you signed up to Zulip with, try checking your email accounts for the "Welcome to Zulip" that was sent to you upon the registration of your account.

2. In the field labeled **Password**, enter your password. Please note that the **Password** field is case-sensitive.

    If you've forgotten your password, see the [Forgot password](#forgot-password) section for instructions on how to reset your password.

3. Once you have finished entering your credentials, click the blue **Login** button to finish signing in.

### Forgot password
If you've forgotten your password, click the **Forgot password?** link below the **Password** field.

![Zulip sign in reset password](/static/images/help/reset-password.png)

After you enter your email address in the **Email** field and click the blue **Reset password** button, you will receive an email similar to the example below.

```
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: 7bit
Subject: Zulip password reset
From: Zulip <zulip@example.com>
To: [your email address]
Date: [timestamp]

Psst. Word on the street is that you forgot your password, [your email address].

It's all good. Follow the link below and we'll take care of the rest:

[password reset link]

Thanks,
Your friends at Zulip HQ
```

## Signing in with your Google account

![Zulip sign in Google](/static/images/help/signin-google.png)

If your organization has enabled Google authentication, you can sign in to your Zulip organization using your Google account by following a few simple steps.

1. Click the blue **Sign in with Google** button located under the **Login** button and **Forgot your password?** link.

2. If you are not signed in to a Google account, Google will ask you to enter the credentials to your Google account.

    ![Zulip sign in Google login](/static/images/help/google-login.png)

3. If you're signing in to Zulip with a Google account for the first time, you will be taken to a page titled **Request for permission**.

    ![Zulip sign in Google Request Permission](/static/images/help/google-request.png)

    Zulip requires knowledge of your email address and basic profile info, such as your name, for login purposes.

4. Click the blue **Allow** button to finish your Google login.

    If you click the **Deny** button, Zulip cannot finish logging you in, and you will be redirected to the Zulip login page.

## Signing in with your GitHub account

![Zulip sign in GitHub](/static/images/help/signin-github.png)

If your organization has enabled GitHub authentication, you can sign in to your Zulip organization using your GitHub account by following a few simple steps.

1. Click the white **Sign in with GitHub** button located under the **Sign in with Google** button.

2. If you are not signed in to a GitHub account, GitHub will ask you to enter your credentials to your GitHub account.

    ![Zulip sign in GitHub login](/static/images/help/github-login.png)

3. If you're signing in to Zulip with a GitHub account for the first time, you will be taken to a page titled **Authorize application**.

    ![Zulip sign in GitHub Request Permission](/static/images/help/github-request.png)

    Zulip requires user data such as your email address and name for login purposes.

4. Click the green **Authorize application** button to finish your GitHub login.
