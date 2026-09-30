# BBMB certificate-chain repair

BBMB sends only its leaf certificate. `godaddy-g2-intermediate.pem` supplies the
missing Go Daddy Secure Certificate Authority - G2 intermediate, obtained on
2026-09-30 over verified HTTPS from:

https://certs.godaddy.com/repository/gdig2.crt.pem

The certificate's DER SHA-256 matches GoDaddy's published repository fingerprint:
`973a41276ffd01e027a2aad49e34c37846d3e976ff6a620b6712e33832041aa6`.
Repository: https://certs.godaddy.com/repository/

This is a public intermediate certificate, valid through 2031-05-03. It is not
the server certificate or a new root. The BBMB-only Requests adapter requires
the chain to terminate at a normal public root from Requests' certificate store;
partial-chain trust is disabled. Hostname and expiry verification remain enabled.
Other hosts and redirect destinations use their ordinary Requests adapters.

If BBMB changes issuers while still omitting intermediates, review the replacement
against the issuer's official repository. Never bypass verification or trust a
downloaded server leaf certificate.
