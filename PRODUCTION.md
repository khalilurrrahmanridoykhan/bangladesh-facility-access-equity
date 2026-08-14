# Production operations

## Public endpoints

- Public map: `https://shasthopath.krrkhan.com/`
- Android download: `https://shasthopath.krrkhan.com/download.html`
- Health check: `https://shasthopath.krrkhan.com/api/health`
- Protected review: `https://shasthopath.krrkhan.com/admin.html`

## Architecture

The Python service and static PWA run as the non-root `app` user in a read-only Docker container. Only `data/reports/` is writable and persistent. The service joins the existing `onehealth-platform_default` Docker network, where the existing Caddy proxy terminates TLS and routes the public hostname to `shasthopath:8080`.

The Android app bundles the same public web assets. Native feedback requests are restricted to the Capacitor origin and sent to the production HTTPS API. Production deployment creates a release-signed APK and places it at `web/downloads/shasthopath-1.0.apk` before rebuilding the service image.

## Server-only secrets

Production secrets live in `/opt/shasthopath/.env.production`, mode `600`. The permanent Android signing key lives outside the repository at `/home/shasthopath/.config/shasthopath/release.jks`, mode `600`. Neither file is committed or uploaded by deployment automation.

Back up the signing key and its passwords securely. Losing it prevents users from installing future updates over the existing app. Never replace the key for later releases.

## Manual deployment

```bash
ssh -i ~/.ssh/shasthopath_vps shasthopath@31.97.144.127
cd /opt/shasthopath
bash scripts/deploy_production.sh
```

Verify after every release:

```bash
curl --fail https://shasthopath.krrkhan.com/api/health
curl --fail --head https://shasthopath.krrkhan.com/downloads/shasthopath-1.0.apk
sha256sum web/downloads/shasthopath-1.0.apk
```

## GitHub Actions

- `CI` runs Python tests, JavaScript syntax checks, and the production dependency audit.
- `Android test APK` creates a short-lived debug APK artifact for pull requests or manual testing.
- `Deploy production` uploads committed source to the VPS, builds the release-signed APK on the VPS, and rebuilds the production container after changes reach `master`.

The repository production environment requires one GitHub secret:

- `VPS_SSH_KEY`: the private deployment key corresponding to `/home/shasthopath/.ssh/authorized_keys`.

Require approval on the GitHub `production` environment if another maintainer joins the repository.

## Amazon Appstore preparation

Upload the release APK, not the Actions debug artifact. Before submission, prepare a public privacy-policy URL, support email, app screenshots, icon artwork, short and long descriptions, content rating answers, and verification evidence for facility/source licensing. Test the exact release APK on low-cost Android hardware before submitting it.
