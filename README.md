# Keep or Skip — official website

Static website publishing repository for **Keep or Skip**.

## Current status

Reviewed static website files are included. Deployment is manual; verify the
latest successful Pages run and public HTTPS responses before calling URLs live.

The source of truth remains private. This repository never receives application
code, private reports, credentials or private Git history.

Expected URLs, **not claimed live**:

- Home: https://tuhuzbayeu.github.io/keep-or-skip-site/
- Privacy: https://tuhuzbayeu.github.io/keep-or-skip-site/privacy/
- Support: https://tuhuzbayeu.github.io/keep-or-skip-site/support/

## Publishing a reviewed update

1. Review the final Privacy Policy and matching application behavior in the
   private source. Verify provider terms, retention and transfers, obtain the
   required controller approval and record the exact policy and file hashes.
2. Use the private source's allowlisted export command into a checkout of this
   repository. It checks approval before writing; it never copies Git history,
   private files or credentials, and never pushes automatically.
3. Review `git diff`. Only `site/`'s eight allowlisted static files, this README,
   `.gitignore`, the checker, manual workflow and `publication.json` belong here.
   Commit through a reviewed pull request. Privacy changes require a new content
   approval; changing one byte invalidates the existing approved snapshot.
4. On main, run `python3 Scripts/check-website.py --publication --review-file
   publication.json`. Until the complete approved export exists, failure is expected.
5. Dispatch **Publish official website** manually. There is no push/PR deployment.
   Only `site/` becomes the Pages artifact. The workflow uses GitHub's short-lived
   token and OIDC; no private-repository PAT or access secret is required.
6. Verify successful deployment and unauthenticated HTTPS responses, actual page
   content and navigation for all three URLs before using them in App Store Connect.

The website uses static HTML/CSS, local assets and system fonts. No website
analytics, tracking scripts, third-party embeds, cookies or external fonts.
GitHub may process connection information to provide hosting.

Developer: Vadzim Tuhuzbayeu · Contact: tuhuzbayeu@gmail.com
