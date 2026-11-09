# Security policy

Report a vulnerability privately through GitHub's "Report a
vulnerability" button on this repository's Security tab. Please do not
open a public issue for it. You will get a reply within 7 days.

Scope: the code in this repository. The harness opens no network
listener; PostgreSQL is reached over a local Unix socket and Qdrant runs
embedded in the same process. No credential is stored in this
repository.
