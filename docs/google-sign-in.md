# Google sign-in

"Sign in with Google" is built into the sign-in and sign-up pages and is
**off until a Google client ID is set**. With no client ID the button is not
shown and `POST /api/v1/auth/google` answers 503.

## What you need from Google (about 10 minutes)

1. Open <https://console.cloud.google.com/> and create a project, for example
   "CAZO EASM".
2. **APIs & Services → OAuth consent screen**
   - User type: External.
   - App name: CAZO EASM. Support email and developer email: yours.
   - App domain: `https://cazoeasm.io`. Privacy policy:
     `https://cazoeasm.io/legal/privacy`. Terms:
     `https://cazoeasm.io/legal/terms`.
   - Authorized domain: `cazoeasm.io`.
   - Scopes: leave the defaults (`openid`, `email`, `profile`). These are not
     sensitive scopes, so Google does not require a security review.
   - Press **Publish app**. While the app is in "Testing", only the test
     users you list can sign in.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**.
   - **Authorized JavaScript origins**: add every address the site is served
     from, exactly, with no path and no trailing slash:
     - `https://cazoeasm.io`
     - `https://www.cazoeasm.io` (if you use it)
     - `http://localhost:3000` (for local development)
   - **Authorized redirect URIs**: leave empty. This flow uses Google's popup
     and never redirects through Google, so no redirect URI is needed.
4. Copy the **Client ID**. It looks like
   `1234567890-abc123.apps.googleusercontent.com`.

No client secret is used. The site receives a signed ID token from Google and
the backend checks the signature and that the token was issued for this
client ID.

## Turning it on

Set one variable on the **backend** service and restart it:

```
GOOGLE_CLIENT_ID=1234567890-abc123.apps.googleusercontent.com
```

The frontend asks the backend (`GET /api/v1/auth/google/config`) which client
ID to use, so no frontend rebuild is needed. `NEXT_PUBLIC_GOOGLE_CLIENT_ID` on
the frontend still works as a fallback but is optional.

To turn it off again, remove the variable and restart.

## How it behaves

| Situation | Result |
| --- | --- |
| New person signs in with Google | Account is created with the email marked verified, then they go to onboarding to create an organization |
| Returning Google user | Signed in, goes to the dashboard |
| Account has MFA enabled | Asked for the MFA code after Google |
| Email already belongs to a password account | Refused with a message to sign in with the password. Google is never linked silently, because that would let anyone controlling a matching Google address take the account over |
| Google reports the email as unverified | Refused |
| Token not signed by Google, or issued for another client ID | Refused |

## Checking it works

1. `curl https://<your-api>/api/v1/auth/google/config` should return
   `{"enabled": true, "client_id": "..."}`.
2. Open `/login`. A Google button appears under the password form.
3. Sign in with a Google account that has no CAZO account. You should land on
   onboarding.

If the button shows but Google says "origin not allowed" or the popup closes
at once, the address in the browser is missing from **Authorized JavaScript
origins** (step 3). Changes there can take a few minutes to apply.

## Known gap

A person who signed up with a password cannot add Google to that account yet.
The refusal message points them to Account Settings, but there is no
"link Google" control there. Until that exists they keep using their password.
