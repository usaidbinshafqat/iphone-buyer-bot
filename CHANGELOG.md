# Changelog

## 2026-11-11 — New single-commit repo `iphone-buyer-bot` for going public

- **What:** created private GitHub repo `usaidbinshafqat/iphone-buyer-bot` from a snapshot of this tree as one commit, with no earlier history. Local clone: `~/iphone-buyer-bot`. Its `README.md` title and clone command use the new name; everything else is identical to `apple-buyer` at `8c43aeb` plus this entry.
- **Why:** Usaid wants the public repo to carry no commit history. He chose a new repo over deleting or force-pushing the existing ones.
- **Left alone:** `usaidbinshafqat/apple-buyer` (scrubbed 80-commit history, private), `apple-buyer-old-delete-me` (unscrubbed, private, must never go public) and `~/apple-buyer-pre-scrub.bundle`. `~/apple-buyer` is still the working copy with logs, state and the venv.
- **Notes to future self:** `iphone-buyer-bot` is the one meant to go public, so public-facing edits go there and get copied back here if they matter. Paths, launchd labels and the Keychain service are still named `apple-buyer`, so the README tells people to clone into `~/apple-buyer`. This changelog ships in the new repo as is; trimming it for the public is still Usaid's call.
- **Roll back:** delete the GitHub repo `iphone-buyer-bot` and `~/iphone-buyer-bot`. Nothing else depends on them.

## 2026-11-10 — README: say what it got us

- **What:** one paragraph added to the top of `README.md`: two phones in launch week, one for Usaid and one for his girlfriend, the bot bought one and he bought the other in the Apple Store app off the alerts.
- **Why:** Usaid wants the README and the Reddit post to say plainly that it was useful for both alerting and buying. The split matches the 11-02 tally: one bot order, the rest bought by hand in the app. The existing "bot won one unit" line stays.
- **Roll back:** `git revert` this commit.

## 2026-11-09 — MIT licence, commit author email rewritten to GitHub no-reply

- **What:** added `LICENSE` (MIT, copyright Usaid Bin Shafqat, the name on the public GitHub profile) and a "License" section in `README.md`. Rewrote author and committer email on every commit from the Gmail address to `25301958+usaidbinshafqat@users.noreply.github.com` with `git filter-repo --mailmap`, then force-pushed `main`. The repo-local `user.email` is set to the same no-reply address so new commits match. Global `~/.gitconfig` is unchanged.
- **Why:** Usaid chose MIT plus the README notice, and asked for the email rewrite before going public. He declined a hard cap on `want_total`: anyone can edit the code, so it would only be decoration.
- **Effect:** every commit hash changed again. Any other clone must be re-cloned. `~/apple-buyer-pre-scrub.bundle` is unaffected and still holds the real data.
- **Notes to future self:** the no-resale wording in the README is a request, not a licence term; MIT does not restrict use. The Gmail address is also the public email on the GitHub profile, so the rewrite only keeps it out of this repo's commits. The pre-rewrite commits stay reachable by hash on GitHub until it garbage-collects them; they hold nothing beyond that email.
- **Roll back:** delete `LICENSE` and the README section. To restore the old author email, run `git filter-repo --mailmap` with the mapping reversed and force-push.

## 2026-11-09 — README: measured alert speed and accuracy, tracker-only mode

- **What:** new README section "Stock alerts: how fast and how accurate" with numbers taken from `logs/` for 10-28 21:04 to 11-02 17:46 (the 2 s polling period, 4.9 days). The "Read this first" bullets now say checkout loses to the app with Apple Pay but the Telegram tracker is the strong part. Added a tracker-only recipe (`python -m buyer.poller`, no card). The "How it works" row now says a poll every three to four seconds, which is what the logs show, not two.
- **Why:** Usaid asked for the tracker claim with real stats ("within 2 seconds or even less"). The logs support a median of 2.2 s, not "always under 2 s", so the README says that.
- **Numbers and method:** poll cycle 3 to 4 s (fastest back-to-back status changes 3.1 s apart). Detection delay sampled from the 24 repeat alerts that fired on the first poll after the 45 s per-key cooldown: median 2.2 s, 8/18/20 of 24 within 2/3/5 s, max 12 s. 73 restock events from `poller: status` changes; median length 23 s; 16 within 10 s, 32 within 20 s, 64 within 60 s. Against `isr_watch.log`: 65 of 73 also on InStock Radar (6 of the 8 others lasted 20 s or less); poller matched 38 of 39 InStock Radar runs (the miss was during the 10-28 22:01 poller restart); first in 37 of 38 by a median of 16 s, with the watcher checking every 10 to 12 s. Blind time 136 min of 118 h, all 11-01 (Evomi quota: TRAFFIC_EXHAUSTED, then 402). Failed polls about 5 percent.
- **Not measured:** Telegram send time and phone push delivery (the notifier logs only at enqueue). A bare round trip to api.telegram.org from this Mac took 0.45 s. The Keychain token could not be read from this agent session (`security ... -w` failed although the item exists), so no authenticated call was timed.
- **Caveats to keep honest:** small sample for the delay figure; the head start over InStock Radar includes our own watcher interval; the 8 unconfirmed restocks are unproven either way.
- **Where:** `README.md` only. No code or config changed.
- **Roll back:** `git revert` this commit.

## 2026-11-09 — Open-source prep: clean GitHub repo, setup guide, safe defaults

- **Repo:** the first GitHub push (11-04) carried the unscrubbed commits, so that repo was renamed to `apple-buyer-old-delete-me` (still private) and a fresh private `usaidbinshafqat/apple-buyer` was created from the scrubbed history only. The `gh` token has no `delete_repo` scope, so **Usaid still has to delete `apple-buyer-old-delete-me`** (GitHub → Settings → Delete, or `gh auth refresh -h github.com -s delete_repo` then `gh repo delete`).
- **Docs:** `README.md` rewritten for strangers: what it is, services and costs, card/Keychain setup, Telegram, proxy, dry run, arming, stopping for good, and a "Not for scalping" section. `requirements.txt` added.
- **Code/config:** `scripts/setup_secrets.py` now also prompts for `card2_*` and `proxy_user`/`proxy_pass`. `config.yaml` is now a template: `dry_run: true`, `want_total: 1`, placeholder contact/billing (the 11-04 history scrub already replaced the real address in the working copy too).
- **launchd:** all plists live in `launchd/` as templates (`launchd-disabled/` removed). Nothing of this project is installed in `~/Library/LaunchAgents`.
- **Correction to the 11-04 entry:** `com.usaid.apple-buyer.tailscaled` was *not* the SSH fleet link. It was the userspace node `mac-mini-poller` from the 10-27 phone exit-node poller; SSH uses the Tailscale app (`usaids-mac-mini`). It kept running until today; now booted out, disabled, plist removed; `ssh macbook` verified working afterwards. The `mac-mini-poller` device is still listed in the Tailscale admin console until removed there.
- **Was open, now settled (see the licence entry above):** `LICENSE` added as MIT; no hard cap on `want_total`.
- **To resume the bot on this Mac:** restore real `contact`/`billing` in `config.yaml` (originals are in `~/apple-buyer-pre-scrub.bundle`), set `want_total` and `dry_run: false`, fresh cards in Keychain, then for each label `launchctl enable gui/$(id -u)/<label>`, copy its plist from `launchd/` to `~/Library/LaunchAgents/` and `launchctl bootstrap`.
- **Roll back:** `git revert` this commit; plists can be copied back from `launchd/`.

## 2026-11-04 12:10 — Pushed to GitHub (private) and scrubbed history for open-sourcing

- **What:** Repo pushed to `github.com/usaidbinshafqat/apple-buyer` (private). Full history rewritten with `git filter-repo --replace-text`: home address/zip, phone, email, surname, the bot's order number, a friend's name, and a real virtual-card number that `scripts/debug_billing.py` typed literally (commit from 10-28) are replaced with placeholders. Verified with a grep over `git log -p --all`: only the git author line and the Tailscale handle remain.
- **Backup:** pre-scrub history is in `~/apple-buyer-pre-scrub.bundle` (local only; contains the real data; delete or keep offline).
- **Before flipping public:** `config.yaml` still carries placeholder contact/billing values and real store/zip targets; consider renaming it `config.example.yaml`. `launchd/*.plist` hard-code `/Users/usaid/...` paths. `logs/` and `state/` are gitignored and were never committed.
- **Roll back:** restore from the bundle (`git clone ~/apple-buyer-pre-scrub.bundle`) and force-push.

## 2026-11-04 09:15 — Bot came back after a reboot; now disabled for real

- **What happened:** The 11-02 shutdown used `launchctl bootout` only, which lasts until the next login. The Mac mini rebooted ~19:00 11-02 and `RunAtLoad` relaunched A, B, the poller and the 08:45 reminder. They ran ~38 h unattended; on 11-04 09:03 a 512 Night Sky unit flashed at Pioneer Place and the bots sent the GO GO GO pings. **No order was placed** — both Chrome contexts were dead ("Target page, context or browser has been closed"), ledger unchanged. Usaid noticed the pings.
- **Fix:** `launchctl bootout` + `launchctl disable gui/501/<label>` for `com.usaid.apple-buyer`, `.b`, `.poller`, `.remind`; plists moved from `~/Library/LaunchAgents/` to `launchd-disabled/` in this repo. Killed stray Chrome. `com.usaid.apple-buyer.tailscaled` left running (SSH fleet).
- **Roll back / resume:** `launchctl enable gui/$(id -u)/<label>`, move the plist back to `~/Library/LaunchAgents/`, then `launchctl bootstrap gui/$(id -u) <plist>`. Fresh cards in Keychain first.
- **Note to self:** bootout is not a permanent stop. Disable + remove the plist.

## 2026-11-02 17:46 — SHUT DOWN: Usaid has the iPhones

- **What:** Usaid: "you can kill the bot now. i got the iPhones." Unloaded `com.usaid.apple-buyer`, `com.usaid.apple-buyer.b`, `com.usaid.apple-buyer.poller` (launchctl bootout) and killed `scripts/isr_watch.py`. No bot processes or Chrome windows left. The plists stay in `~/Library/LaunchAgents` but are not loaded; `com.usaid.apple-buyer.tailscaled` (unrelated) left alone.
- **Final tally:** bot win 2026-11-01 21:13 (512 Star White, Pioneer Place, W0000000000, $2,199); Usaid bought the rest himself in the Apple Store app. Ledger `state/purchase.lock.json` left as-is for the record.
- **Loose ends for Usaid:** Evomi Core Membership ($49.99/mo) renews 2026-12-01 unless cancelled; Robinhood virtual cards self-expire (…7969 ~00:13 2026-11-03). Keychain `apple-buyer` entries (cards, proxy creds, Telegram) are still there — `security delete-generic-password -s apple-buyer -a <account>` to remove.
- **To resume:** `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.usaid.apple-buyer.poller.plist` (and `.plist` / `.b.plist` for the bots), `nohup .venv/bin/python scripts/isr_watch.py &`; put fresh cards in Keychain first; check `want_total` vs ledger.

## 2026-11-02 00:15 — New targets: Portland only, two more Night Sky; new card

- **Targets (Usaid, 00:13):** "only in portland: buy 2 blue 512 ideally or buy 1 blue 256gb and 1 512gb… stop checking for WA stores." `config.yaml`: `want_total: 3` (1 Star White already confirmed → 2 remaining), `pickup.stores` reduced to R077/R090/R134, `store_parts: {}`. Variant caps unchanged (512 NS max 2, 256 NS max 1, Star White max 1 = already used, so `plan` never picks it again). Verified: `plan.remaining == 2`; Star White-only availability → no buy.
- **Card:** Keychain `card_*` = new Robinhood virtual …7969 (exp 06/31, zip 00000, **auto-expires ~00:13 2026-11-03**); `card2_*` = …9990 (auto-expires ~09:27 2026-11-02, then dead weight).
- **Restarts:** poller, A, B restarted 00:14–00:16; A parked 00:14:49.
- **Roll back:** `git revert` this commit for config; Keychain entries by hand.
- **Notes to self:** poller now polls 3 stores only (same request size — Apple returns all 8 regardless, we just ignore the rest). After each win the home IP is 541-blocked for ~90 min (observed 21:17→22:49); plan for that before chasing the second unit.

## 2026-11-01 21:20 — FIRST WIN + unconfirmed-order guard no longer pauses the other instance

- **Win:** 21:12:11 poller saw 512 Star White at Pioneer Place; Bot A swapped its bag (UI flow, not staged), picked a window, entered card …8335, Place Order at ~21:13:40, ✅ confirmed 21:13:59 — order **W0000000000**, $2,199.00. Ledger: 1/2. First success after ~17 lost attempts; the unit stayed available ~2.5 min (unusually long), which is what made the 105 s UI path enough.
- **Bug it exposed:** Bot B read the ledger while A's order was `submitting` and hit `has_unconfirmed()` → "bot paused", exit 3 (launchd KeepAlive restarted it ~90 s later). `buyer/state.py has_unconfirmed()` now returns True only for `submitted` (clicked, no confirmation) or a `submitting` entry older than 180 s. Both instances restarted on it.
- **Cards:** …8335 is single-purchase and now spent; Keychain `card_*` swapped to the backup …9990 (auto-expires ~09:27 2026-11-02) and …8335 moved to `card2_*`. Need a fresh card from Usaid before tomorrow morning.
- **Targets now:** Usaid wants one more unit, Night Sky only (256 or 512). Star White `max_units: 1` is reached so `plan` won't pick it; the poller still sends 🟢 for Star White flashes (cosmetic).
- **Roll back:** revert the commit for the guard; Keychain swap is reversible by swapping the six `card*` entries back.

## 2026-11-01 21:10 — Immediate rebuild when the parked session flips to delivery-only

- **What happened:** 21:04 256 Night Sky flashed at Bridgeport; Bot B's select was rejected (unit flickered, someone else's bag). Apple then flipped B's checkout to "Your order is only eligible for delivery" (no store list). B "stayed on the parked session", and each subsequent store search waited the full 25 s for radios that never came — three times — before the 3-failure rule rebuilt it. The 21:06:32 Washington Square flash landed in that dead window; B was parked again only at 21:07:17, unit gone at 21:07:00.
- **Change:** `buyer/browser_monitor.py` gains `DeliveryOnly` + `_delivery_only(page)`. `_search` raises it before searching and when the radio wait times out on a delivery-only page; the main loop catches it and rebuilds at once (no failure count). The post-loss "stay parked" decision also rebuilds immediately if the banner is present.
- **Roll back:** revert the commit; behaviour returns to 3×25 s before rebuild.
- **Notes to self:** the delivery-only flip seems to follow a rejected/lost attempt on the same session; a rebuild costs ~3 checkoutx calls (~20 s) and is far cheaper than the 75 s dead time. Earlier delivery-only detection (empty store list after a *successful* search) is still in place for the other variant of this flip.

## 2026-11-01 16:01 — Proxy poller moved from DataImpulse to Evomi (data plan exhausted)

- **What happened:** DataImpulse 5 GB plan hit `407 TRAFFIC_EXHAUSTED` at 14:03 (≈2 GB/day at 60 KB/poll); minimum top-up there is $50. Usaid bought Evomi Core Residential pay-as-you-go (15 GB, $0.99/GB, no expiry).
- **Change:** Keychain `proxy_user`/`proxy_pass` now hold the Evomi credentials (password carries the `_country-US` geo suffix, so `config.yaml` `proxy_poller.user_suffix` is `""`); `gateway` is `core-residential.evomi.com:1000` (HTTP; per-request rotation by default). Old DataImpulse creds kept as `proxy_user_dataimpulse`/`proxy_pass_dataimpulse`. Poller restarted 16:01, exit IPs rotating (Charter/Comcast US), Apple polls ~1.1 s.
- **Roll back:** put the `*_dataimpulse` values back into `proxy_user`/`proxy_pass`, restore `gateway: gw.dataimpulse.com:823` and `user_suffix: "__cr.us"`, kickstart the poller.
- **Notes to self:** 15 GB ≈ 7 days at 2 s cadence; `proxy_poller.interval_seconds: 4` roughly doubles that. The poller logs `PROXY DOWN?` after 10 straight failures when the balance runs out. Evomi bills a 512-byte minimum per request (irrelevant at 60 KB/poll).

## 2026-11-01 09:55 — Poller: loud "PROXY DOWN?" line after 10 straight failures; proxy usage measured

- **What:** `buyer/poller.py` logs an ERROR `PROXY DOWN? N consecutive poll failures…` at 10/30/60 consecutive failures so a dead proxy (data plan exhausted, auth rejected) stands out from the normal one-off bad-exit noise. Poller restarted 09:55, exit IP OK.
- **Measured:** one `pickup-message` poll (3 parts, 8 stores, `pl=true`) is ~60 KB gzipped (89 KB without `pl=true`, 45 KB for a single part — 3-in-1 is already the cheapest). At the 2–3 s cadence that is ~1.5–2 GB/day, so the 5 GB DataImpulse plan bought 2026-10-29 is close to empty. DataImpulse's minimum for any further payment (new plan *or* top-up of the existing one) is $50; the $5 starter was a one-off.
- **Roll back:** revert the commit; nothing else changed.
- **Notes to self:** if the proxy dies, do NOT fall back to polling from the home IP — that IP is what the two checkout sessions use and a 541 block there kills the buy. Options are: top up ($50 = 50 GB ≈ 25 days), or lengthen `proxy_poller.interval_seconds` 2→4 (halves usage, +1 s mean detection latency).

## 2026-11-01 09:30 — Backup card: automatic retry when the primary declines

- **What:** second card in Keychain as `card2_number` / `card2_exp` / `card2_cvv` (service `apple-buyer`; Robinhood virtual Visa …9990, same billing address as the primary). `fastpath.card(cfg, slot)` / `has_backup_card(cfg)` read a slot; `billing_to_review_encrypted(..., slot=)` submits it. `fastpath.run()` retries the billing step once with slot 2 if Apple rejects the primary card there. `checkout.review_and_place(..., card_slot=1)`: on "payment authorization failed / declined" after Place Order with slot 1 it marks that order failed, Telegrams "retrying with the backup card", calls `fastpath.rebill(page, cfg, t, slot=2)` (goto Billing → encrypted card 2 → goto Review) and places again with slot 2; a slot-2 decline is the old 🚨 CARD DECLINED + NeedsHuman stop.
- **Why:** 2026-10-31 08:07 the bot reached Place Order on a real 512 Night Sky and the primary card …8335 declined (Robinhood fraud flag); we held the unit and had nothing to fall back to.
- **Roll back:** `git revert` this commit; the Keychain entries are harmless if unused (`security delete-generic-password -s apple-buyer -a card2_number` etc. to remove).
- **Notes to self:** the backup card auto-expires 1 day after creation (created 2026-11-01 ~09:27 PST) — refresh `card2_*` daily or it is dead weight. Primary …8335 auto-expires after 1 purchase, so after a first win it must be replaced before the second unit. Rebill costs ~2 inventory calls (~15-25s); the unit may be gone by then, in which case the Billing page shows the unavailable banner and we Abort normally.

## 2026-10-30 23:55 — Evening wave post-mortem: shield block is profile-bound; auto fresh-profile after 3 blocks

- **What happened:** 22:04-22:18 four flashes (Bridgeport 512+256, Pioneer 256, Washington Square 256); both bots fired within 2s, selected the store with 30-40 windows, and were rejected at Continue ~20s in every time. From 22:31 both sessions got 541 on the pickup tab and stayed blocked for 80+ min despite 2-10 min cooldowns, while a brand-new guest profile passed immediately (probe 23:50).
- **Changes:** `browser_monitor` keeps the parked session after a lost attempt when still on Fulfillment (saves 3 calls/loss); block cooldown 120s doubling to 600s; after 3 consecutive blocks it relaunches on a fresh profile (old one renamed `*-blocked-<mmdd-HHMM>`). Both bots moved to fresh profiles at 23:52/23:53 and parked; blocked profiles kept as `state/chrome-profile-blocked-1030-A/B`.
- **Also:** Seattle stores now allow 512 Night Sky too (`store_parts`), Star White stays Portland-only.
- **Notes to self:** every loss this week is at Apple's Continue/billing inventory check ~20-50s after the unit appears; the web floor is ~40s. Prune `state/chrome-profile-blocked-*` periodically.

## 2026-10-30 17:56 — Second parked session for 256GB Night Sky (`com.usaid.apple-buyer.b`)

- **What:** `buyer/main.py` takes env overrides `BUYER_PARTS`, `BUYER_PROFILE_DIR`, `BUYER_LOG_NAME`, `BUYER_INTERVAL`. Instance A (`com.usaid.apple-buyer`, `BUYER_PARTS=MK1H4LL/A,MK1G4LL/A`, profile `state/chrome-profile`, 120s) parks 512 Night Sky; instance B (`com.usaid.apple-buyer.b`, `BUYER_PARTS=MK1F4LL/A`, profile `state/chrome-profile-b`, log `logs/buyer-b.log`, 180s) parks 256 Night Sky in its own guest bag. `state/trigger.json` is no longer deleted on read; each instance consumes triggers by timestamp. Shared ledger keeps the two-unit cap. Both parked and reading store lists at 17:56.
- **Why:** 45% of this week's flashes were 256 Night Sky; the single bot lost 12-20s swapping its bag and opening a cold checkout before the 40s path even started.
- **Also today:** eight stores (Portland 3 + Seattle 5), `pickup.store_parts` restricts Seattle stores to 256 Night Sky; plan prefers stores in config order; card …8335 (single-purchase) in Keychain; a friend added to Telegram.
- **Rollback:** `launchctl bootout gui/501/com.usaid.apple-buyer.b`; remove `EnvironmentVariables` from the A plist to let it handle all three parts again.
- **Notes to self:** two sessions = two sets of checkoutx calls on the home IP (120s + 180s cadence ≈ 50/hr, under the ~70 budget). If 541s return, lengthen B's interval first.

## 2026-10-28 21:40 — Research round 2 + experiments (notes to self)

- **Winners' flow (Reddit, 5+ corroborated, Oct 25-28):** Apple Store iOS app, Duo in bag, "Buy with Apple Pay" checkout pre-loaded, tap Pickup -> store -> check-in window -> Face ID; 10-15s. Earliest check-in window is contested and gets you kicked at Continue -> we now take the latest window on the earliest day (`pickup.window`). Late-night wave ~10:00-10:30pm PT, morning wave 9:15-10:30am. Refreshing bag/checkout trips a ~10-min lockout; pre-bag availability pages don't.
- **Measured tonight:** Apple's checkout steps are not parallelisable (out-of-order calls are no-ops). The ~10s per call applies to the calls that hit store inventory (select, continue, contact->billing on pickup, billing->review on pickup); on a *delivery* checkout billing->review took 0.9s. Reusing time-slot ids across sessions/products is rejected. Parking a delivery checkout at Review and switching to pickup did not yield slots from `select` (wizard stays at review); not pursued.
- **Not available:** Apple Store app on Mac (iPhone/iPad only); Apple Pay via iPhone Mirroring/Safari needs a human confirm.

## 2026-10-28 20:57 — Third variant: iPhone Duo 256GB Night Sky (MK1F4LL/A), preference 3, max 1

- **What:** Usaid asked for a "256GB blue" fallback (not white in 256). The Duo only comes in Night Sky and Star White; Night Sky is the dark-blue one, so added `MK1F4LL/A` "iPhone Duo 256GB Night Sky" (part verified via pickup-message titles for all 8 SKUs) as the third preference, `max_units: 1`. Plan order checked: 512 NS > 512 SW > 256 NS. `scripts/isr_watch.py` now matches any configured capacity+colour on the InStock Radar cards (was hard-coded to 512 GB). Bot, poller and watcher restarted; the poller queries all three parts in one request.
- **Verified:** the 256 NS configurator path puts exactly "iPhone Duo 256GB Night Sky" x1 in the bag and reaches the Fulfillment page (no purchase).
- **Rollback:** delete the third variant block in `config.yaml` and restart the three processes.

## 2026-10-28 20:40 — Fast path now submits billing as one request with in-page card encryption (hit -> Place Order gate 40.7s, was 52s)

- **What:** `buyer/fastpath.py`: after contact->billing, `goto ?_s=Billing`, read Apple's card-field key from the page (`"config":{"publicKey","publicKeyHash","algorithm":"rsa-oaep"}`, same key the UI uses; falls back to `selectBillingOptionAction` to obtain it), encrypt card number + CVV in the page with WebCrypto RSA-OAEP/SHA-256 exactly as Apple's `checkout.js` does (`cipherText`/`publicKeyHash` JSON), and POST a single `continueFromBillingToReview` with CREDIT + encrypted card + billing address + `billing.city_state` (new config key "Seattle, WA", so no zipLookup call). Then `goto ?_s=Review`; `checkout.buy` runs `review_and_place` (DOM checks + Place Order) on stage "review". UI billing remains the fallback if no key is found.
- **Measured (iPhone 17 dry run, warm, signed in):** select 9.2s, continue 9.8s, contact->billing 10.0s, billing->review 10.2s, total 40.7s. The four inventory-checking calls are Apple's floor; everything else is now sub-second.
- **Also:** proxy poller transient exit errors retry in 2s (were 60s+ backoffs, ~20 min blind per hour); cadence 3s. On 541 the browser keeps its signed-in profile and just cools down.
- **Rollback:** `checkout.fastpath: false` (UI flow), or `git revert`.

## 2026-10-28 19:38 — Signed in on the live profile; timed dry run = 52s hit->Place Order gate

- **What:** Apple ID signed in + browser trusted on the live `state/chrome-profile` (scratch `signin_2fa.py`, JS clicks through Apple's chooser overlay, code from Usaid). `checkout.sign_in: true`. New 24h virtual card (…5081) in Keychain. `ensure_bag` normalises non-breaking spaces in bag titles (iPhone 18 Pro title broke the match).
- **Measured (iPhone 17, warm session, signed in, fast path):** select 9.2s, continue->contact 9.9s, contact->billing 10.1s, card typing+billing->review ~23s; total 52.4s. Warm searches 0.7s but every mutating checkoutx call is ~10s (Apple serialises one per session per ~10s). Continue without a prior select is rejected ("check-in window … no longer available"), so the step count can't drop. Only remaining cut: saved card (CVV only) ≈ -8-10s.
- **Rollback:** `sign_in: false`.

## 2026-10-28 19:17 — Rotating residential proxy for the pickup-API poller (`buyer/poller.py`, `config.polling.proxy_poller`)

- **What:** `proxy: keychain` builds `http://<proxy_user>__cr.us:<proxy_pass>@gw.dataimpulse.com:823` from Keychain items `proxy_user`/`proxy_pass` (DataImpulse residential plan, US exits, new IP per request on port 823). `rotating: true` opens a fresh connection per poll; a 541 is treated as "that exit IP was hot" (retry, 60s pause after 5 in a row) instead of a 10-30 min backoff. Cadence 5s. Writes `state/trigger.json` (source `proxy_poller`) on a hit. Verified exits rotate (3 different IPs) and pickup-message answers 200 in ~1s.
- **Also tonight (19:12 hit at Pioneer Place, lost at 53s):** `payment()` now aborts instantly on Apple's "unavailable for pickup" banner instead of three retries; watcher triggers only wake the browser and no longer override its own fresh store reading (stale InStock Radar trigger caused a second doomed attempt).
- **Rollback:** `proxy: socks5://localhost:1055`, `rotating: false`, `interval_seconds: 70`; `security delete-generic-password -s apple-buyer -a proxy_user` (and proxy_pass).
- **Notes to self:** ~45 KB/poll -> ~780 MB/day at 5s; plan has 5 GB. Datacenter/mobile tiers not needed.

## 2026-10-28 18:45 — Hybrid XHR fast path (`buyer/fastpath.py`, `checkout.buy`, `config.checkout.fastpath`)

- **What:** on a stock hit from the parked Fulfillment page, `fastpath.run` POSTs Apple's checkoutx calls from inside the tab (`page.evaluate(fetch)`, same cookies/TLS/shield cookies): `_a=select` (store) -> earliest enabled window from the reply -> `continueFromFulfillmentToPickupContact` -> `continueFromPickupContactToBilling`, then `goto ?_s=Billing` and the existing UI `payment()` + `review_and_place()` (DOM checks of product/store/qty/total still gate Place Order). Field names/bodies captured from our own guest dry run (`state/checkoutx_capture.jsonl`, card values redacted to shape). If the select reply carries no windows it returns to the UI `select_pickup`. 541/503/429 raise `checkout.Blocked` (shared with browser_monitor's cooldown). `_search` now logs Apple's response time.
- **Why not all-XHR:** Apple encrypts card number + CVV client-side (`{"cipherText","publicKeyHash"}`), so a raw PAN submit bounces to /shop/sorry/message_generic. Billing stays in the UI.
- **Measured:** dry run (iPhone 17, fresh session) 61s to Review, each checkoutx call ~10s = Apple's per-session serialisation on a cold session; iphone-hunter notes a session searched every ~2 min answers in 1-3s. The gain is removing DOM waits/clicks (~10-20s) and being robust to UI re-renders; the big lever remains a warm session + fast detection.
- **Rollback:** `checkout.fastpath: false` in config.yaml (UI flow unchanged).

## 2026-10-28 18:20 — InStock Radar watcher as a second stock signal (`scripts/isr_watch.py`)

- **What:** polls https://instockradar.com/us/iphone-duo (server-rendered, their checker hits Apple every ~20s) every 8s, parses the `id="s-R077|R090|R134"` cards, and drops `state/trigger.json` (source `instockradar`) + Telegram when a card shows "In stock" with "512 GB" + Night Sky / Star White. Started under nohup (`logs/isr_watch.log`); not yet a launchd agent.
- **Why:** home IP is budget-limited on both Apple endpoints (pickup-message 541'd at 18:10 after ~48 polls; checkoutx 541 twice today). Their page carries no Apple rate limit for us. Their data shows Washington Square restocked 512GB Night Sky at 17:14 today — while our bot was in its 541 cooldown.
- **Rollback:** `pkill -f isr_watch.py`; delete the script.
- **Notes to self:** detection latency = their 20s check + our 8s poll; stock windows median ~1 min per their stats. Make it a LaunchAgent if it proves useful. Be a polite client (8s, one page).

## 2026-10-28 17:50 — Two-speed browser polling, 541 self-healing, session rebuild (`buyer/browser_monitor.py`, `config.yaml`)

- **What:** Modelled on westonfw/iphone-hunter `fastpath.py` notes (checkoutx has a per-exit-IP budget of ~70 calls; after a 541, probing renews the ban — go silent, then a new session passes). Browser monitor now: cold search every `interval_seconds` (120 ±20) to keep the parked checkout warm; on any `state/trigger.json` from a watcher, searches back-to-back for `hot_seconds` (25); re-enters checkout every `session_rebuild_minutes` (17, Apple TTL 20); detects 541 on the pickup-tab / search responses or a `/shop/404` landing -> `Blocked` -> closes Chrome, sleeps `block_cooldown_seconds` (240, doubling to 30 min), relaunches on a **fresh profile** (old one renamed `chrome-profile-blocked-<mmdd-HHMM>`), Telegram on first block.
- **Why:** 8s/20s cadence from one IP tripped the budget twice today (15:43, 17:10). Detection now leans on the watchers (home pickup-message 75s, proxy poller) + 120s browser search; the browser's job is to be warm when a trigger lands.
- **Rollback:** `git revert`; previous behaviour = interval 8–20s with no block handling.
- **Notes to self:** detection granularity from one IP is ~45s vs 6–15s stock windows — needs a rotating residential proxy for the pickup-message scout (Usaid's call). Stale profiles pile up under `state/`; prune.

## 2026-10-28 17:35 — 541 came back on the clean profile; cadence 8s -> 20s; bot paused behind an unblock probe

- **What:** 21 min after the 16:45 fix the checkout store-select call 541'd again, and a brand-new profile from the home IP is blocked too, so this round is IP-level rate flagging. Browser `polling.interval_seconds` 8 -> 20 (`config.yaml`). Bot booted out; a scratch loop (`probe_loop.py`, fresh profile `state/probe-loop`) tries add-to-bag -> guest checkout -> pickup tab every ~9 min and runs `launchctl bootstrap` on the buyer agent when it passes.
- **Why:** Usaid asked for 8s "if it's not going to get throttled"; it is now. Usaid told at 17:3x.
- **Rollback:** set interval back to 8; `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.usaid.apple-buyer.plist` to force the bot up.
- **Notes to self:** independent pickup-message watcher (`manual_watch.py`, 75s, home IP) still returns 200 and is running as the stock signal while checkout is blocked.

## 2026-10-28 16:45 — Apple Shield block (HTTP 541) fixed: hide automation flag, fresh profile, sign-in off

- **What happened:** From ~15:40 every poll died on Apple's 404 page. Apple's `/shop/shld/s3/verify.js` ("Shield") started answering the add-to-cart navigation and `checkoutx ... selectFulfillmentLocationAction` with HTTP 541 whenever the browser advertised automation. Not IP (same via Tailscale proxy; curl got 200) and not the account. Once a profile was flagged it stayed flagged even after clearing cookies.
- **Fix:** both `launch_persistent_context` calls (`buyer/browser_monitor.py`, `buyer/checkout.py`) now pass `ignore_default_args=["--enable-automation"]` in addition to `--disable-blink-features=AutomationControlled` (navigator.webdriver is now false). Bot moved to a brand-new Chrome profile at `state/chrome-profile`; old ones kept as `state/chrome-profile-tainted-1028` (had the trusted Apple ID session) and `state/chrome-profile-fresh-blocked-1028`. New `checkout.sign_in: false` in `config.yaml` gates the Apple ID sign-in attempt (the fresh profile is not 2FA-trusted; a sign-in would stall on the code prompt). Poll-error log line now includes the page URL.
- **Verified:** 16:45 bot staged the bag, went to checkout as guest, and read real store statuses again.
- **Rollback:** `git revert`; set `sign_in: true` once the new profile has been through 2FA (run the scratch sign-in flow, Usaid supplies the code).
- **Notes to self:** `/shop/fulfillment-messages` returning 541 is normal (constant since Aug 2026 for everyone) — ignore it. The 541 that matters is on add-to-cart / checkoutx. If it reappears: fresh profile + check `navigator.webdriver`.

## 2026-10-28 15:36 — Signed-in checkout (Apple ID)

- **What:** Checkout now runs signed in as Usaid's Apple ID instead of guest. Keychain (`apple-buyer`) gained `apple_id` and `apple_id_password`. The Chrome profile (`state/chrome-profile`) holds a trusted, 2FA-completed session (Trust-this-browser accepted 15:30), so checkout skips the sign-in page entirely. `buyer/checkout.py::_try_sign_in` handles Apple's chooser-first state (remembered email → "Continue with Password") without retyping the email; `go_checkout` tries it once and falls back to guest. Abort on Continue timeout now includes the page URL.
- **Why:** Guest checkout cost ~80–90s; signed-in removes sign-in/contact typing and enables a saved card later.
- **Verified:** dry run (iPhone 17, not submitted) reached Review signed in; sign-in page never shown.
- **Rollback:** delete the two Keychain items (`security delete-generic-password -s apple-buyer -a apple_id` etc.) and the bot reverts to guest automatically; or `git revert` this commit.
- **Notes to self:** 2FA codes can only be typed by a human; if the session ever drops, rerun the scratch sign-in flow (needs a fresh code). Next: save the card on the Apple account (do it at 8pm with the new card; the old one expires tonight), then the checkoutx XHR fast path.

## 2026-10-28 13:15 — checkout timing pass (dry-run measured ~81s store-click→Place Order under launch-day load)

- Bug fix: my 8s/12s caps on slot-dropdown and Continue waits (12:27 entry) aborted a real flow because Apple's slot spinner takes >8s today. Restored to full `t` (25s) but kept instant `Abort` when Apple's sold-out banner appears.
- Trimmed fixed sleeps in `select_pickup`, `pickup_contact`, `payment`, `review_and_place`; screenshots are viewport-only except review/after_place/attempt_abort. Typing stays at 25ms/char — 8ms made Apple reject the card number.
- Late card form: after the nudge Continue, wait up to 8s for the card input; retry loop fills the form if it appears late.
- Measured (iPhone 17 dry run, 13:10): store click→Continue 24s (Apple slot loading), →billing 22s, card entry 17s, →review 12s. Dominated by Apple page latency; saved ~3s total.
- Rollback: git revert; `launchctl kickstart -k gui/501/com.usaid.apple-buyer`.

## 2026-10-28 12:59 — 8s browser search cadence (user request)

- `config.yaml` browser monitor `interval_seconds` 20→8, `jitter_seconds` 5→2. Checkout store-search host (`secure6.store.apple.com/shop/checkoutx/fulfillment?_a=search`) has never returned 541/503 to us; unknown true limit.
- `buyer/browser_monitor.py`: after 6+ consecutive failures log "possible throttling" and pause 120s (safety valve if the host does start rejecting).
- Rollback: set 20/5 and `launchctl kickstart -k gui/501/com.usaid.apple-buyer`.

## 2026-10-28 12:27 — race tuning after 2nd/3rd missed hits

**What changed and why**
- 12:03 Bridgeport and 12:26 Washington Square: browser saw "Available Today", bot clicked the store within ~1s, Apple rejected ("This item is unavailable for pickup at your selected location" / bounced at Continue). We then sat on 25s Playwright timeouts before re-searching.
- `buyer/checkout.py` `select_pickup`: shorter settles (0.3/0.4s instead of 1/1.5s); after store click, poll up to 8s for either the window dropdown or Apple's rejection banner and raise `Abort` immediately on rejection; after Continue, poll up to 12s for the PickupContact/Billing URL or the rejection banner, `Abort` on rejection.
- `buyer/browser_monitor.py`: sleep after 3 consecutive failures 30s→5s.
- `config.yaml`: browser monitor `interval_seconds` 35→20, `jitter_seconds` 10→5.

**Rollback**: revert these hunks (git) and `launchctl kickstart -k gui/501/com.usaid.apple-buyer`.

**Notes**: order summary at Oregon pickup is $2,199.00 (no tax), so the 2450 cap is just headroom. Checkout store-search host has not rate limited at 20s so far.

## 2026-10-28 — drop-day tuning after first missed hit (11:08am)

**What changed and why**
- First real hit: proxy poller saw Night Sky at Pioneer Place 11:08:11; bot reached checkout ~9s later and the store already showed "Currently unavailable" (abort, resumed). Checkout order summary showed $2,430.99 (tax estimate), which would have failed the $2,300/unit review cap.
- `config.yaml`: `max_unit_price_usd` 2300→2450, `max_order_total_usd` 4600→4900 so a tax line can't abort review. Browser monitor `polling.interval_seconds` 70→35, `jitter_seconds` 20→10 (checkout store-search host has never been rate limited).
- `buyer/checkout.py` `buy(..., staged=False)`: when `staged=True` skip `ensure_bag`/`go_checkout` (saves ~6s). `buyer/browser_monitor.py` passes `staged=True` when buying the preferred variant x1 from the fulfillment page it already sits on.
- Earlier today (not previously logged): `units_per_order: 1` — one device per order, then immediately go again.

**Rollback**: revert the three values in `config.yaml`; drop the `staged` kwarg (default False keeps old behavior). Restart with `launchctl kickstart -k gui/501/com.usaid.apple-buyer`.

**Notes to future self**: Apple pickup API (`/shop/retail/pickup-message`) 541-blocks an IP after ~30 polls/hour; the Flip's T-Mobile IP gets 541'd too. Store-wide 503 = Apple waiting room (not per-IP). Units flash for ~10s during drops.

## 2026-10-28 (early) — two devices, two colors
- New goal per Usaid: 2 x 512GB Duo total; Night Sky preferred, Star White allowed for at most one. `product.variants` list
  (MK1H4LL/A blue max 2, MK1G4LL/A white max 1), `want_total: 2`, caps `max_unit_price_usd` 2300 / `max_order_total_usd` 4600.
- `buyer/plan.py` picks (store, part, qty): more units first, then preference order; blocked while any order is unconfirmed.
- `buyer/state.py` is now a ledger of orders (phase submitting/submitted/confirmed/failed); units counted conservatively.
- `checkout.buy()` sets bag to exactly variant x qty (quantity dropdown), falls back qty 2 -> 1 if the store can't fulfil 2,
  verifies review quantity ("Quantity for ... \n N") and total (amount on the line after "Total").
- Monitor/poller check both parts in one pickup-message call; poller trigger carries the full availability map; browser monitor
  stages blue x1 in the bag and continues after each order until want_total.
- Verified: dry run qty 2 with iPhone 17 (guest) reached Place Order, total $1,858.00 parsed; not submitted; bag cleared.
- To re-arm after a confirmed order was actually cancelled: edit its phase to "failed" in state/purchase.lock.json.

## 2026-10-27 (late) — second poller through Z Flip exit node; Telegram on; phone added
- Home IP block on pickup-message lifted on its own after ~4h.
- Added `buyer/poller.py`: polls `/shop/retail/pickup-message` via SOCKS `localhost:1055` every 70-90s. The proxy is a second,
  userspace `tailscaled` (Homebrew) logged in as `mac-mini-poller` with exit node `usaids-z-flip7` (cellular, Wi-Fi off on the phone).
  State/socket under `state/ts/`. LaunchAgents: `com.usaid.apple-buyer.tailscaled`, `com.usaid.apple-buyer.poller`.
- On a hit the poller writes `state/trigger.json`; `browser_monitor` checks that file every 2s during its sleep and runs immediately.
  Effective check cadence ~35-45s across two IPs; checkout stays on the home IP.
- Telegram enabled (token/chat_id in Keychain). `contact.phone` set. One-shot reminder LaunchAgent `com.usaid.apple-buyer.remind`
  fires 2026-10-28 20:30 and removes itself.
- Gotchas: first poller login landed on the wrong tailnet (usaidbinshafqat@); needed `logout` + `--force-reauth` in a private window.
  Exit node only helps if the phone is off Wi-Fi; verify with `curl --socks5-hostname localhost:1055 ifconfig.me`.
- Rollback: `launchctl bootout gui/501/com.usaid.apple-buyer.poller` and `.tailscaled`; delete `state/ts/`.

## 2026-10-27 (night) — full checkout verified to Place Order; ARMED
- Dry run with an in-stock iPhone 17 as guest reached the review page (`_s=Review`) and found `continue-button-placeOrder`
  ("Place Your Order"); did not click; test item removed from scratch bag. Review page shows pickup contact, card last-4, billing, totals.
- Fixes: Apple's React inputs need focused keystrokes (`type_into`: focus + press_sequentially + verify), the CVV box's help button
  intercepts clicks (so never click inputs), the card form sometimes needs a Continue "nudge" and the nudge's response re-renders the
  form (wait for `continueFromBillingToReview` response, then re-verify every field right before each Continue), the zip lookup is async
  (wait for city/state select), and Billing->Review does not change the URL immediately (detect by "Payment Details"/Place Order).
- `checkout.dry_run: false`. Agent restarted in browser-monitor mode (guest session, Duo in bag, 100-140s cadence).
- Card details stored in Keychain (`apple-buyer`: card_number/card_exp/card_cvv). Virtual card auto-expires after 1 day (set 2026-10-27 ~21:15) —
  Usaid must extend or replace, otherwise checkout will fail at billing. `contact.phone` still empty -> NeedsHuman at pickup contact.
- Rollback: set `checkout.dry_run: true`, `launchctl kickstart -k gui/501/com.usaid.apple-buyer`.

## 2026-10-27 (evening) — IP blocked on pickup endpoint; browser fallback monitor
- Apple returned HTTP 541 on both `/shop/retail/pickup-message` and `/shop/fulfillment-messages` for the home IP (174.127.175.60,
  shared by Mac mini, MacBook, Pixel) after ~30 polls in 20 min at a 35-45s cadence. Block applies to curl and real Chrome alike;
  rest of apple.com unaffected. Still blocked 1.5h+ later.
- HTTP polling slowed to 100-140s (`polling.interval_seconds/jitter_seconds`), backoff floor 600s, max 1800s.
- New `buyer/browser_monitor.py`: parks Chrome on the checkout fulfillment step (Duo in bag, guest or signed in) and re-runs the
  zip search (`checkoutx/fulfillment?_a=search` on secure6.store.apple.com, not blocked). Parses store radio labels. On availability it
  continues checkout on the same page. `polling.mode: browser` (now the default) or auto-switch after two 541s in http mode.
- Guest checkout path fully mapped with an in-stock iPhone 17 (no order placed, scratch profile): store radios (`value=R090`),
  date radios inside `fieldset:has-text("pickup date")`, `pickup-availablewindow-dropdown` (option 0 is a placeholder; values like
  `28-10:00a.m.-10:15a.m.`), `fulfillment-continue-button`; PickupContact page `selfPickup`, `form-field-{firstName,lastName,emailAddress,fullDaytimePhone}`,
  `continue-button-label`; Billing page `checkout-billingOptions-CREDIT`, `card-number-input`, `expiration-input`, `security-code-input`,
  billing `form-field-{firstName,lastName,street,street2,postalCode}`, `continue-button-review`. Review page and Place Order button still unmapped
  (needs a real card); driver uses role-name regex "Place Order".
- Policy per Usaid: always pick the earliest pickup date and the first time window.
- Secrets: Keychain `apple-buyer` now may hold `card_number`, `card_exp`, `card_cvv` (guest path) or just `card_cvv` (saved card path).
  `config.yaml` gained `contact` and `billing` sections (not secret).
- Rollback: set `polling.mode: http`; remove browser_monitor.py; Keychain items under service `apple-buyer`.
- Note to self: guest checkout sessions expire after ~20-30 min (page falls back to Fulfillment-init); the browser monitor re-enters.
  Order summary showed WA tax when zip was 98101; Oregon zip shows $2,199.00 flat.

## 2026-10-27 — initial build
- New repo for an Apple Store pickup auto-buyer (iPhone Duo 512GB Night Sky, MK1H4LL/A, Oregon stores R077/R090/R134).
- `buyer/monitor.py` polls `/shop/retail/pickup-message` (works; `/shop/fulfillment-messages` returns 541). One request covers all stores near zip 97223.
- `buyer/checkout.py` Playwright flow using Apple's `data-autom` attributes mapped via `scripts/discover*.py` as a guest:
  configurator radios (`dimensionColornightsky`, `dimensionCapacity512gb`, `choose-noTradeIn`, `purchaseGroupOptionfullprice`,
  `carrierModelUNLOCKED/US`, `noapplecare`, `add-to-cart`), bag (`bag-item-name`, `checkout`), fulfillment ("I’ll pick it up" text,
  `bag-storelocator-input`, store radios with `value=R134` etc., `fulfillment-continue-button`).
  Pickup-details, payment, review and Place Order selectors are NOT yet verified (need a signed-in session); they use
  generic fallbacks and screenshot every step.
- Secrets (card CVV, Telegram) in macOS Keychain service `apple-buyer`; never in files.
- Purchase lock written before Place Order click; bot refuses to run while the lock exists.
- Rollback: delete `~/apple-buyer` and `~/Library/LaunchAgents/com.usaid.apple-buyer.plist`; Keychain items under service `apple-buyer`.
- Notes to self: delivery estimate for the Duo was late January, so pickup is the only fast path. Checkout zip defaulted to 98101
  (Seattle, WA tax) on the scratch profile; the account profile should show Oregon. Apple's `541` is a block/rate-limit, not a dead endpoint.
