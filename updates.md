# Jiran account and inventory experience updates

Status: implementation checkpoint; browser validation and live deployment are in progress.

## Implemented

1. Replaced the locked contact screen with editable full name, phone number and store name.
2. Added account-context refresh so saved names and preferences propagate without signing out.
3. Added store creation for accounts with no store, plus a usable state after store deletion.
4. Added location creation, editing and removal, including address, city, country, map preview and optional coordinates. Zero coordinates remain valid; missing values are no longer treated as zero.
5. Added explicit device-location permission flow with manual-entry fallback.
6. Added password changes with current-password verification, confirmation and visible feedback. Login email remains managed by the owner in this team demo.
7. Added notification and dashboard preferences with keyboard-accessible checkboxes and saved feedback.
8. Added visible product creation, editing and deletion actions. Product saves now write complete inventory records rather than silently creating marketplace listings.
9. Added typed-name confirmation for product and store deletion, with keyboard-accessible native dialogs, focus restoration and cancellation.
10. Added atomic, account-scoped backend operations for these workflows, input validation and recent-account activity.
11. Product deletion preserves historical orders, removes stale ML results and cancels affected listing requests. Store deletion removes store records but retains the login account and personal profile.
12. Added protection against leaving Settings via navigation with unsaved edits, plus browser reload/close warnings.
13. Added responsive account forms, loading feedback, inline errors, clear empty states and accessible labels.
14. Connected account widgets to Settings and corrected brand links for GitHub Pages paths.
15. Added database checks for valid coordinates, nonnegative stock/prices, ownership of stock connections, and RPC-only destructive deletion.

## Verification

- Frontend production build: passed at implementation checkpoint.
- Disposable-account database integration: passed profile persistence, location create/edit/remove, zero-coordinate handling, product create/edit/delete, invalid-input rejection, cross-account denial, store delete/recreate and retained login.
- Browser end-to-end verification: in progress.
- The three team demo stores are not used for destructive testing.

## Research boundaries

These changes provide functional prototypes and test evidence. They are not results of a participant usability study. Source-data authenticity and independent ML validation remain unconfirmed, as documented in `docs/TEAM_DEMO.md` and `docs/ML_CHANGES.md`.

## Version control

The existing local Git repository is retained. Implementation and validation checkpoints record source, migrations, test scripts and this document. Passwords, environment files, raw/normalized store data, test credentials, reports derived from private data and generated model artifacts remain outside commits.
