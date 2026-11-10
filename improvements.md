# Improvements

## Implemented and verified

1. **Connected team demo:** GitHub Pages reaches the local Supabase application through an authenticated Python gateway and HTTPS tunnel.
2. **Working team logins:** Three retailer accounts have populated dashboards and account-scoped inventory access.
3. **Editable profiles:** Full name, phone number and store name can be saved and persist across reloads.
4. **Store lifecycle:** Accounts can create a store, delete it with exact-name confirmation, and create a replacement while retaining their login.
5. **Location management:** Set, edit and remove the primary store location, with address, city, country, valid coordinates and map links.
6. **Optional device location:** Browser permission is requested only when selected, with manual-entry fallback.
7. **Account security:** Current-password verification, confirmation, password visibility controls and saved/error feedback.
8. **Preferences:** Keyboard-accessible controls for inventory alerts and the top-sellers dashboard widget.
9. **Product management:** Visible create, edit and delete actions backed by complete transactional inventory writes.
10. **Guarded deletion:** Typed product/store names, cancellable accessible dialogs, focus handling and clear explanations of what will be removed.
11. **Historical integrity:** Product deletion retains historical orders and invalidates obsolete predictions and recommendations.
12. **Tenant isolation:** Owner checks, database policies and restricted gateway endpoints prevent one account from modifying another store's private records.
13. **Validation:** Nonnegative prices/stock, unique SKUs, required names, coordinate bounds, and rejection of invalid ML inputs.
14. **Usability feedback:** Loading states, useful empty states, inline errors, success notices and a responsive settings layout.
15. **Unsaved-edit protection:** Settings header navigation and reload/close warnings protect unfinished edits. Browser Back is a remaining limitation.
16. **SVG icon system:** Emoji graphics replaced with consistent Lucide icons; decorative icons are hidden from assistive technology and icon buttons have accessible names.
17. **Navigation:** Account widgets open Settings, and brand links respect the GitHub Pages base path.
18. **Traceable activity:** Account-scoped records of profile, location, store and product changes.
19. **Atomic ML publication:** Prediction jobs publish to the dashboard tables consistently; a failed batch retains the previous results.
20. **Forecast improvements:** Fill missing calendar days explicitly and select between weekly baseline, recent mean and regularized Prophet using historical validation.
21. **Classifier improvements:** Stronger tree regularization and training-fold-only simulations of stock, demand and inactivity edge cases.
22. **Evaluation:** Product-group validation, class metrics, temporal forecast backtests, baseline comparisons and reproducible synthetic stress tests. Development F1 measures policy agreement, not independently reviewed business outcomes.
23. **Version control:** Local Git checkpoints and a pushed recovery branch, with `updates.md` and `HANDOFF.md` recording progress. Secrets, source data and generated models remain outside Git.
24. **Database administration:** Local Supabase Studio is available at `http://127.0.0.1:54323/project/default/editor` while its container is running.

## Archive recovery completed

25. **Recover the supplied archive:** `/Users/zoro/Projects/Jiran/Private/archives/Jiran-user-20261110.zip` has been extracted safely and fingerprinted outside the source repository.
26. **Restore the missing large transaction history:** Its nested `ml:sample.zip` contains approximately 1 GB of transactions, alongside 2,555 catalog products and 5,960 stock records across 50 stores. The complete file contains 17,025,416 validated transaction lines; uniqueness, numeric values and product/store relationships passed checks.
27. **Separate data provenance:** The archive documentation explicitly describes the large dataset as generated. Keep it separate from the existing three-store dataset, whose original authenticity remains unconfirmed.
28. **Rebuild missing artifacts:** The archive contained no saved `.pkl` or `.joblib` files. New research artifacts were trained and tested in isolation; the live demo model was not replaced.
29. **Reconcile database contracts:** The archive's research `products` schema conflicts with the live application's product identifiers and relationships. Recovered tables now live in the isolated `jiran_archive_lab` schema, containing 2,555 products, 5,960 stock records, 1,013,393 daily sales rows, forecasts and classifications. The live public tables were not overwritten.

## Remaining improvements requiring further work or evidence

30. **Permanent team hosting:** Replace the temporary Mac-dependent tunnel with a stable hosted backend or named tunnel and domain.
31. **Independent business validation:** Confirm source authenticity, add independent stores and dated stock snapshots, and obtain retailer-reviewed outcomes.
32. **Forecast large-error reduction:** MAE improved in development tests, but RMSE worsened and sparse-demand errors remain high. More independent temporal evaluation is needed.
33. **Manual refresh:** Replace legacy POS sync calls with inventory reloads for imported/manual sources.
34. **Full navigation protection:** Extend unsaved-edit handling to browser Back navigation.
35. **Additional account features:** Owner-managed email changes, full account deletion, multiple stores and uploaded-document management require separate implementation.
36. **POS connectors:** Restore and test Square/Apideck only when their credentials and backend services are available.
37. **Research study:** Run participant usability testing and record task completion, errors and feedback. Functional checks are not substitutes for a user study.

## Additional recovery findings

38. **Future-data exclusion:** Found 80,369 transactions later than the stock snapshot. Snapshot features exclude those records, and automated tests verify the cutoff.
39. **Local research API:** Rebuilt archive models run separately at `http://127.0.0.1:8003/docs`; scenario requests do not write to production.
40. **Explicit candidate limits:** The archive classifier's high policy-agreement score does not make it production-ready. It failed the 365-day-inactivity stress scenario; policy/model disagreement is exposed for review.
41. **Research validation:** Classifier evaluation holds out complete stores, and forecast evaluation uses rolling future windows with series selection performed before the first test window. Generated data is never described as independently collected business evidence.


## Workspace and continuity

42. **One canonical project:** `/Users/zoro/Projects/Jiran` now contains the source, data, archives, evidence, historical copies and deployment checkout. Existing paths are compatibility links.
43. **GRC synchronized:** Updated the previously stale project identity/status, recorded completed milestones and added concrete remaining work with a current handoff.
44. **Clear entry points:** `START_HERE.md`, `REMAINING.md`, `Jiran.code-workspace` and `GRC_DASHBOARD.html` make the project easy to reopen and navigate.
45. **Private-data separation:** Credentials, raw data and nested repository history are local under `Private`; only source, docs, tests, migrations and safe GRC metadata are pushed.
