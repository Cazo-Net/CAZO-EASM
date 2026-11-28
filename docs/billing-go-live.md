# Going live with payments

This is the checklist for switching CAZO EASM billing from Stripe **test mode**
to **live** payments. The plans, checkout, webhooks and limits are already built
(see `docs/billing.md`). What remains is account setup and configuration.

Run the readiness check at every stage. It reads your configuration and Stripe
account and never charges anything:

```bash
# on the deployed backend (Railway shell, docker exec, ...)
python -m app.billing.readiness
```

Platform superusers can also call `GET /api/v1/billing/admin/readiness`.
Live payments are ready when it prints `READY`.

## Who does what

| Step | Who |
|---|---|
| Open and activate a Stripe account in the company's name, verify identity, add a payout bank account | **Owner only** |
| Decide MYR prices and whether to charge SST | **Owner** (with an accountant) |
| Turn on payment methods (cards, FPX, GrabPay) and the customer portal in the Stripe Dashboard | **Owner**, about 5 minutes |
| Create the webhook endpoint in Stripe and copy its secret | **Owner** (Dashboard), or Claude with Stripe access |
| Set environment variables on the backend | **Owner** (Railway), or Claude with deploy access |
| Code: webhook handler, live-key guard, MYR/FPX support, tax toggle, readiness check | Done |

## 1. Stripe account (owner)

1. Create the account at dashboard.stripe.com with **Malaysia** as the country.
   Stripe's Malaysia terms accept businesses, including sole proprietors,
   located in Malaysia. Stripe Payments Malaysia Sdn. Bhd. is the contracting
   party.
2. Complete **Activate payments**. Stripe asks for:
   - business name, address and website (the public CAZO site, with the pricing page, terms and privacy policy linked)
   - the **SSM Business Registration Number (BRN)**
   - your **Tax Identification Number (MY TIN)**, and an **SST ID** if you are registered
   - identity documents for the representative and owners
   - a **bank account at a Malaysian bank**, owned by the business, for payouts
3. In **Settings > Business > Tax details**, enter the BRN, TIN and SST ID.
   Without these, Stripe cannot issue you government-verified e-invoices for
   its own fees.
4. Wait until the Dashboard shows charges and payouts enabled. The readiness
   check reports this as `stripe_account`.

**E-invoicing:** Stripe issues MyInvois e-invoices only for *its own fees*.
E-invoices for your sales to customers are your responsibility; ask your
accountant how to file them with LHDN.

## 2. Prices and currency (owner decides)

- **USD**, the current default, works with cards from a Malaysian account and
  needs no change. FPX cannot be offered in USD.
- **MYR** is needed for FPX and GrabPay. Set `BILLING_CURRENCY=myr` and give
  every plan an MYR price in `BILLING_PLANS_JSON`. Amounts are monthly, in sen.
  This example converts at about 4.5 MYR per USD; choose your own numbers:

```json
{"essentials": {"prices": {"myr": 225000}},
 "business":   {"prices": {"myr": 450000}},
 "plus":       {"prices": {"myr": 900000}},
 "mssp":       {"prices": {"myr": 90000}},
 "addon_extra_domain": {"prices": {"myr": 45000}}}
```

  That means RM 2,250, 4,500 and 9,000 a month, RM 900 per MSSP client, and
  RM 450 per extra root domain. The readiness check fails if any plan has no
  price in the chosen currency.

- **Tax (SST):** if you must charge it, set up **Stripe Tax** with your
  registration in the Dashboard, then set `BILLING_AUTOMATIC_TAX=true`.
  Otherwise prices are charged as listed.

## 3. Dashboard settings (owner, live mode)

The test and live modes have separate settings, so do these with the
Dashboard switched to **live**:

1. **Settings > Payment methods**: keep **Cards** on. With MYR prices, turn on
   **FPX** and optionally **GrabPay**. FPX shows up only under
   "Pay for one term", because Stripe does not support FPX for automatic
   renewals.
2. **Settings > Billing > Customer portal**: activate it, and allow updating
   payment methods, viewing invoices and cancelling. This powers the
   "Open Stripe billing portal" button.
3. **Settings > Branding**: logo and colours for Checkout and receipts.
4. **Settings > Emails**: turn on receipts for successful payments.

## 4. Webhook endpoint

In **Developers > Webhooks** (live mode), add an endpoint:

- **URL:** `https://<your API domain>/api/v1/billing/webhook`
- **Events:** `checkout.session.completed`,
  `checkout.session.async_payment_succeeded`,
  `customer.subscription.created`, `customer.subscription.updated`,
  `customer.subscription.deleted`, `invoice.paid`, `invoice.finalized`,
  `invoice.payment_failed`, `invoice.voided`, `invoice.marked_uncollectible`

Copy the endpoint's **signing secret** (`whsec_...`) into
`STRIPE_WEBHOOK_SECRET`. A live endpoint has a different secret from the test
one.

The handler checks Stripe's signature, ignores events it has already
processed, and records each event in `billing_events`.

## 5. Switch the backend to live

Set these on the backend service, for example in Railway's Variables tab, then
redeploy:

```
STRIPE_SECRET_KEY=sk_live_...        # or a restricted key rk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...      # from the LIVE endpoint
BILLING_ALLOW_LIVE_KEYS=true         # without this, live keys are refused
FRONTEND_URL=https://<dashboard domain>
BILLING_CURRENCY=usd                 # or myr plus BILLING_PLANS_JSON
BILLING_ENFORCE_LIMITS=true
# optional
BILLING_AUTOMATIC_TAX=true
```

Never commit live keys to the repository, and never paste them in chat.

## 6. First live payment

1. Run `python -m app.billing.readiness` and confirm it prints `READY`.
2. In the Dashboard, send a test webhook event to the live endpoint. The
   readiness check then shows `webhook_delivery: OK`.
3. Buy the smallest plan (Essentials, quarterly) with a real card on your own
   organization. Check that `/billing` shows the plan, and that the payment and
   receipt appear in Stripe.
4. Refund it from the Stripe Dashboard if you want, and cancel the renewal on
   `/billing`.
5. With MYR, repeat with **FPX** under "Pay for one term".

## Going back to test mode

Set `STRIPE_SECRET_KEY` to the `sk_test_...` key and `STRIPE_WEBHOOK_SECRET`
to the test endpoint's secret, then remove `BILLING_ALLOW_LIVE_KEYS`. Live and
test customers are separate in Stripe. Existing `billing_subscriptions` rows
created in one mode will not match objects in the other.
