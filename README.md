# iphone-buyer-bot

A personal Apple Store **in-store pickup** watcher and auto-checkout bot for macOS. It was built to get an
iPhone Duo at launch, when pickup stock appeared for seconds at a time. It watches a few stores for a few
exact part numbers, pings you on Telegram the moment one shows up, and tries to complete a guest checkout
for pickup in a real Chrome window.

It got me two phones in launch week, one for me and one for my girlfriend. The bot bought one on its own.
I bought the other myself in the Apple Store app, with its Telegram alerts telling me when stock appeared.

It is a snapshot of something that worked in October and November 2026. Apple changes its store often, so
expect selectors and endpoints to need fixing. `CHANGELOG.md` is the full lab notebook: what broke, what
was measured and why each decision was made.

## Read this first

- **Personal use only.** This is for buying a device you will use. It is not for resale. See
  [Not for scalping](#not-for-scalping).
- **You are automating a store that does not want to be automated.** Apple may block your IP, cancel an
  order or refuse a sale. You use this at your own risk and on your own account and card.
- **It ships safe.** `checkout.dry_run` is `true`, so the bot stops at the Place Order button and takes a
  screenshot. Nothing is bought until you change that.
- **Honest results on checkout.** Over six days of launch-week drops the bot won one unit. Half of all
  restocks were gone within 23 seconds and the web checkout cannot finish in under about 40 seconds. A
  person with the Apple Store app and Apple Pay is faster at the buying part.
- **Where it is strong: the stock tracker.** The poller sends a Telegram alert a median of 2.2 seconds
  after Apple's pickup feed changes. It beat a public stock tracker to the same restock 37 times out of
  38, by a median of 16 seconds. You can run the tracker alone and buy in the app yourself. See
  [Stock alerts: how fast and how accurate](#stock-alerts-how-fast-and-how-accurate).

## How it works

| Piece | Command | What it does |
|---|---|---|
| Checkout bot | `python -m buyer.main` | Keeps a real Chrome window parked on Apple's checkout pickup step with the item in the bag. Re-checks your stores every two minutes. On a hit it selects the store and pickup window, fills contact and billing, verifies the review page and places the order. |
| Stock poller | `python -m buyer.poller` | Polls Apple's pickup availability endpoint every three to four seconds through a rotating residential proxy. Sends the Telegram alert and wakes the checkout bot. |
| Second signal | `python scripts/isr_watch.py` | Optional. Watches the public InStock Radar page for your stores. Free and uses no Apple quota. |
| Ledger | `state/purchase.lock.json` | Every attempt and order. The bot refuses to buy past your configured total and pauses if an order is left unconfirmed. |

Before Place Order the bot checks the item title, quantity, store and order total against `config.yaml`
and aborts on any mismatch. It never attempts to pass a CAPTCHA, a two-factor prompt or a bank
verification screen. It stops, screenshots and messages you instead.

Two rules learned the hard way:

- **Never poll stock from the IP you check out from.** Apple rate limits per IP with an HTTP 541, and a
  blocked IP cannot buy. Polling goes through the proxy. Checkout never does.
- **Two checkout sessions per IP is the ceiling.** More than that and Apple blocks all of them.

## Stock alerts: how fast and how accurate

These numbers come from this project's own logs for 28 October to 2 November 2026, the 4.9 days the
poller ran at a two-second interval against Apple Stores in the Portland area.

| Measure | Result |
|---|---|
| Poll cycle | About 3 to 4 seconds: a 2 second sleep, up to 1 second of jitter and about 1 second for the request through the proxy. The fastest back-to-back polls were 3.1 seconds apart. |
| Delay from Apple's feed changing to the alert | Median 2.2 seconds. 8 of 24 samples were within 2 seconds, 18 within 3 seconds and 20 within 5 seconds. The worst was 12 seconds. |
| Telegram hand-off | About half a second for a round trip to Telegram's API from the same Mac. Push delivery to the phone was not measured. |
| Restocks seen | 73 in 4.9 days. |
| How long a restock lasted | Median 23 seconds. 16 were gone within 10 seconds, 32 within 20 seconds and 64 within a minute. The shortest one caught lasted 3.3 seconds. |
| Confirmed by a second source | 65 of the 73 also appeared on InStock Radar. Of the 8 that did not, 6 lasted 20 seconds or less. |
| Restocks missed | Of 39 restocks InStock Radar showed, the poller caught 38. The miss fell during a poller restart. |
| Head start over InStock Radar | First 37 times out of 38, by a median of 16 seconds. |
| Blind time | 136 minutes out of 118 hours, or 1.9 percent, all on one day when the proxy data ran out. |
| Failed polls | About 5 percent. A bad proxy exit fails one poll and the next poll uses a new exit. |

How to read them:

- **An alert means Apple's own feed said "available".** The poller alerts only when the pickup feed
  reports the part as available at that store and the product title in the reply matches the model in
  `config.yaml`. It does not mean the unit will still be there when you tap Buy.
- **The delay figure is an estimate from a small sample.** The poller repeats an alert on the first
  poll after a fixed 45 second cooldown. The overshoot past 45 seconds shows how long a change waits
  for the next poll. There were 24 such repeats.
- **The head start is partly ours to give.** `scripts/isr_watch.py` checked the InStock Radar page every
  10 to 12 seconds, so some of the 16 seconds is that check interval and not InStock Radar's own lag.
- **The 8 unconfirmed restocks are not proven either way.** A slower tracker is expected to miss short
  flashes, but nothing in the logs shows whether those units were real.
- **Speed costs proxy data.** A shorter interval finds stock sooner and uses more data. See
  [Proxy usage](#what-you-need-and-what-it-costs).

**Tracker only.** To get the alerts and buy by hand, do setup steps 1, 3 and 4 and run only the poller.
In `scripts/setup_secrets.py` leave the card prompts blank.

```bash
.venv/bin/python -m buyer.poller
```

It needs the Telegram and proxy secrets and no card. Leave `checkout.dry_run: true`. The five-ping
"GO GO GO" burst is tied to one part number in `buyer/poller.py`. Every other variant gets a single
alert. Change that part number to the one you want most.

## What you need and what it costs

| Need | What we used | Cost |
|---|---|---|
| A Mac that stays awake | Mac mini | Already owned. macOS is required because secrets live in Keychain and the services run under launchd. |
| Google Chrome and Python 3.12 | | Free |
| Alerts | A Telegram bot from @BotFather | Free |
| Rotating residential proxy for the poller | Evomi Core Residential | About $1 per GB pay-as-you-go when we bought it. See usage below. |
| Second stock signal | InStock Radar public page | Free |
| A card you are happy to hand to a script | A virtual card from your bank | Free |

**Proxy usage.** One poll is about 60 KB. That is 1.5 to 2 GB a day at a 2 second interval, or under 1 GB
a day at 5 seconds. A launch week costs roughly $10 to $15. Notes from buying it:

- Evomi sells a monthly membership and a pay-as-you-go balance. Pay-as-you-go is the cheap one. The
  membership free trial cut us off after about 110 MB.
- DataImpulse also works and is about $1 per GB, but its minimum top-up was $50.
- Any gateway that gives a new US residential IP per request will do. Datacenter IPs get blocked.
- Free alternative: a phone on cellular as a Tailscale exit node with `proxy: socks5://localhost:1055`.
  It is one IP, so it needs a much slower interval.

Prices are what we saw in November 2026. Check them before you buy.

## Setup

```bash
git clone https://github.com/usaidbinshafqat/iphone-buyer-bot ~/apple-buyer && cd ~/apple-buyer
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p state logs
```

The paths in `config.yaml` and the launchd files assume `~/apple-buyer`, so clone into that folder even
though the repo has a different name.

### 1. Say what to buy and where

Edit `config.yaml`:

- `product.variants`: one entry per acceptable model, in order of preference. Each needs the part number,
  the exact title Apple shows, the product page URL and the configurator options to click. `max_units`
  caps that variant.
- `product.want_total`: the bot stops for good after this many confirmed units.
- `product.max_unit_price_usd` and `max_order_total_usd`: the order is aborted above these.
- `pickup.zip` and `pickup.stores`: the search zip and the only stores the bot may pick. Store numbers
  such as `R077` are the `storeNumber` values in Apple's pickup availability response.
- `contact` and `billing`: your pickup contact and the **billing address of the card**. They must match
  what your bank has or Apple rejects the card.

### 2. Set up the card

Use a virtual card, not your real card number. Most banks and card apps can issue one. Give it a limit
just above the order total if your bank allows that.

```bash
.venv/bin/python scripts/setup_secrets.py
```

The script asks for each value without echoing it and stores it in the macOS login Keychain under the
service `apple-buyer`. Nothing is written to a file or a log. Leave a prompt blank to skip it, so you can
rerun the script later to replace just one card.

| Keychain item | What it is |
|---|---|
| `card_number`, `card_exp`, `card_cvv` | Primary card. Expiry as `MM/YY`. |
| `card2_number`, `card2_exp`, `card2_cvv` | Optional backup card. If the primary is declined at Place Order the bot re-enters billing with this one and tries again while it still holds the unit. |
| `telegram_bot_token`, `telegram_chat_id` | Alerts. See step 3. |
| `proxy_user`, `proxy_pass` | Residential proxy login. See step 4. |

Things that cost us a phone:

- **A decline at Place Order loses the unit.** Our bank flagged the first large guest charge as fraud.
  Keep a backup card loaded and watch for your bank's approve-this-charge message.
- **Single-use and one-day virtual cards go stale.** A single-use card is dead after the first order and
  a one-day card is dead the next morning. Replace them before the next drop.
- Both cards use the one billing address in `config.yaml`.

To check an item exists without printing it, and to remove one:

```bash
security find-generic-password -s apple-buyer -a card_cvv
security delete-generic-password -s apple-buyer -a card_number
```

### 3. Telegram alerts

1. Message @BotFather, send `/newbot` and copy the token.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<token>/getUpdates` and copy `chat.id`.
4. Run `scripts/setup_secrets.py` again and enter both. Several chat ids can be separated by commas.

### 4. Proxy for the poller

Buy a small pay-as-you-go balance, then store the username and password with `scripts/setup_secrets.py`.
In `config.yaml` under `polling.proxy_poller`, set `gateway` to the provider's host and port. Providers
put the country selector in different places: Evomi appends `_country-US` to the password, DataImpulse
appends `__cr.us` to the username through `user_suffix`.

### 5. Dry run

```bash
.venv/bin/python -m buyer.main --force-checkout R134
```

This walks the checkout for the named store up to Place Order, saves screenshots under `state/shots/`
and buys nothing. While the item is out of stock the run stops at the pickup step, which is still enough
to confirm the bag, the contact fields and that no human prompt appears.

### 6. Arm it

Set `checkout.dry_run: false`, then install the services:

```bash
sed -i '' "s|/Users/usaid|$HOME|g" launchd/*.plist
cp launchd/com.usaid.apple-buyer.plist launchd/com.usaid.apple-buyer.poller.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.usaid.apple-buyer.poller.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.usaid.apple-buyer.plist
```

The bot plist limits itself to certain part numbers through the `BUYER_PARTS` variable. Edit it to match
your config or delete it. `com.usaid.apple-buyer.b.plist` is a second session for another variant with
its own Chrome profile. The tailscaled and remind plists are only for the phone exit-node poller and a
one-off card reminder.

## Running it

- Logs are in `logs/`. `buyer.log` is the bot and `poller.log` is the stock poller.
- Do not restart the bot while stock is flashing. A restart kills the attempt in progress.
- After an order, Apple may block your IP for about 90 minutes even on a fresh Chrome profile. Unload the
  bot and load it again later.
- If the ledger holds an order the bot could not confirm, it pauses. Check apple.com/orders, then edit
  `state/purchase.lock.json`.

**Stopping it for good.** `launchctl bootout` only lasts until the next login. To make it stay off:

```bash
for l in com.usaid.apple-buyer com.usaid.apple-buyer.b com.usaid.apple-buyer.poller; do
  launchctl bootout gui/$(id -u)/$l; launchctl disable gui/$(id -u)/$l
  rm -f ~/Library/LaunchAgents/$l.plist
done
```

## Not for scalping

This was written by someone who wanted a phone, was beaten to it by resellers, and does not want to hand
them another tool. Please do not use it to buy for resale.

Nothing in an open repository can enforce that, but the design does not help a reseller either:

- One unit per order and a hard stop at a small configured total, recorded in a ledger.
- One identity: one contact, one billing address, guest checkout. There is no account or address rotation.
- Checkout runs from your own IP in a visible browser. Proxies are used for reading stock only.
- No CAPTCHA solving and no bypass of bank or two-factor checks.
- Apple's per-IP limits cap it at two sessions.

Apple's sales policy also limits sales to end customers, and Apple reserves the right to cancel orders it
believes are for resale.

## License

MIT. See [LICENSE](LICENSE). The licence lets anyone use, change and share the code. The request not to
use it for resale is a request, not a licence term.
