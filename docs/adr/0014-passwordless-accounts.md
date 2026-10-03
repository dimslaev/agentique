# 14. Accounts have no password; one sign-in link that never expires

## Status

Accepted.

## Context

There were two separate ways in: the newsletter "Subscribe" box (email only,
no account) and a signup form (full name, email, password) that did not
subscribe you. Readers had to pick between them, and the account side carried
password login, recovery, reset and change-password screens for a site whose
only signed-in feature is liking articles.

## Decision

- **Signup takes an email and nothing else.** `POST /users/signup` creates the
  account, adds the address to the newsletter (row plus Resend contact), and
  emails a welcome with the sign-in link. An address that already has an
  account just gets its link again, so the answer never says who has one.
- **The link is a stored random token, `user.login_token`.** It never expires.
  Signing in (`POST /login/link`) emails the same token again, so every link
  ever sent keeps working. `POST /login/token` swaps it for the usual JWT
  access token, which still expires on `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Stored, not a stateless JWT,** so it can be revoked: replacing the column
  kills every old link, and deleting the account kills it with the row.
- **No passwords anywhere,** the first superuser included. `hashed_password`,
  `FIRST_SUPERUSER_PASSWORD` and the recovery, reset and change-password
  endpoints and screens are gone.

## Consequences

- Anyone with access to a reader's inbox, or a forwarded email, is signed in as
  them for good, until the token is replaced by hand. Accepted: an account
  holds likes and a name, nothing worth more than that.
- The superuser signs in by link like everyone else.
