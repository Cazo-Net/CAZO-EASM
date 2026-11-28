# Billing

CAZO EASM sells plans through Stripe. This page covers the plans, how limits are
enforced, and how to set up payments in test mode. To switch to real payments,
follow [billing-go-live.md](billing-go-live.md).

## Plans

From the business plan (27 Nov 2026). Prices are per month, billed per term
(annual = 12 months, quarterly = 3 months).

| Plan | Price (USD) | Root domains | Hosts | Scheduled scans | Users\* | Scans/month\* |
|---|---|---|---|---|---|---|
| Trial (every new org) | free | 1 | 50 | weekly | 2 | 10 |
| Essentials | 500 | 3 | 250 | weekly | 5 | 100 |
| Business | 1,000 | 10 | 1,000 | daily | 15 | 400 |
| Plus | 2,000 | 25 | 3,000 | daily | 40 | 1,000 |
| MSSP (min 10 clients) | 200 per client | 3 per client | 250 per client | daily | unlimited | 100 per client |
| Extra root domain | 100 each | +1 | | | | |

\* Not in the business plan. These are the confirmed defaults (27 Nov 2026).

The catalog lives in `backend/app/billing/plans.py`. Change any price or limit
without a code change by setting the `BILLING_PLANS_JSON` environment variable
on the backend and restarting it. Only the keys you give are replaced. Limit
keys are `root_domains`, `hosts`, `users` and `scans_per_month`; `null` means
unlimited. For example:

```json
{"business": {"prices": {"usd": 100000, "myr": 450000}, "limits": {"users": 20}},
 "addon_extra_domain": {"prices": {"myr": 45000}}}
```

Prices are in the smallest currency unit (cents, sen).

## What is enforced

Checks live in `backend/app/billing/entitlements.py`. When a limit is hit the
API answers **HTTP 402** with `detail.code = "plan_limit_reached"`, and the web
app shows the message with "Upgrade plan" and "View usage" buttons.

- **Root domains**: distinct registrable domains (example.com, example.com.my)
  the organization monitors. A domain counts when it is scanned, added as a
  domain or wildcard scope, or used in an ad-hoc Scanner v2 scan in the last 30
  days. Adding a new one is refused on every path once the allowance is used:
  scans, Scanner v2 scans (REST and live stream), schedules, monitors and the
  Scopes page. A refused scan does not leave an auto-registered scope behind.
  Subdomains of a counted domain are always free. To free a slot, remove the
  domain's scopes and scans.
- **Over the allowance** (after a downgrade or an expired term): the oldest
  root domains up to the allowance keep working; the rest are **paused** and
  shown as such on the Billing page. Paused domains cannot be scanned, and their
  schedules are skipped (the owner gets a notification). Nothing is deleted.
- **Hosts**: hosts in the inventory. Over the allowance, new root domains are
  refused; existing ones keep scanning.
- **Scans per month**: scans created since the 1st (UTC), including ad-hoc
  Scanner v2 scans. Scheduled runs count toward the number but are never
  stopped by it, so monitoring does not silently stop.
- **Scheduled scan frequency**: weekly plans cannot schedule more often than
  every 168 hours, daily plans every 24 hours. This is checked across all
  schedules on the same root domain, so several weekly schedules cannot add up
  to a daily one. After a downgrade, existing schedules run at the new plan's
  frequency.
- **Users**: active members plus pending invitations, checked when inviting,
  when accepting, when SSO creates a user, and when an admin re-enables a user.

Plan changes: checkout refuses (HTTP 409, `plan_change_over_limit`) a plan
whose allowances are below what the organization already uses, unless the
request carries `accept_over_limit: true`. The checkout page lists what is
over and asks the customer to confirm. Organizations on a staff-managed
(manual) plan cannot start an online checkout; they are told to contact CAZO.
The organization's `plan` field is set by billing only; clients cannot set it.

`BILLING_ENFORCE_LIMITS=false` turns all checks off. A plan keeps working for
`BILLING_GRACE_DAYS` (default 7) after a failed renewal or the end of a term,
then the org falls back to Trial limits. Nothing is deleted.

## Payment options

- **Card, renews automatically**: Stripe Checkout in subscription mode.
- **Pay for one term**: Stripe Checkout in payment mode, one payment for the
  whole year or quarter, no auto-renewal. This is the route for one-off local
  methods.
- **Manual** (bank transfer, design partners, staff): a platform superuser calls
  `POST /api/v1/billing/admin/organizations/{org_id}/plan` with
  `{"plan": "business", "period_end": "2027-12-31T00:00:00Z", "note": "..."}`.

Stripe chooses which payment methods to show from those enabled in the
Dashboard (Settings > Payment methods), so no code change is needed to add one.

### Malaysia: FPX and GrabPay

Checked against Stripe's docs on 27 Nov 2026:

- FPX works only for a **Malaysian Stripe account**, in **MYR**, for customers in
  Malaysia, and needs a Malaysian business registration number.
- FPX does **not** support recurring payments or subscriptions. It works in
  Checkout payment mode, so it appears under "Pay for one term".
- To offer it: set `BILLING_CURRENCY=myr`, add MYR prices through
  `BILLING_PLANS_JSON`, and enable FPX (and GrabPay if wanted) in the Dashboard.
- FPX has no disputes; refunds are bank credits and can take weeks.

Cards work in every setup.

## Test-mode setup

1. In the Stripe Dashboard, switch to **Test mode** (or create a sandbox) and
   copy the secret key (`sk_test_...`).
2. Set `STRIPE_SECRET_KEY` on the backend. Live keys are refused unless
   `BILLING_ALLOW_LIVE_KEYS=true`.
3. Add a webhook endpoint pointing at
   `https://<api host>/api/v1/billing/webhook` with these events:
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.paid`, `invoice.finalized`,
   `invoice.payment_failed`, `invoice.voided`, `invoice.marked_uncollectible`.
   Copy its signing secret into `STRIPE_WEBHOOK_SECRET`.
   Locally: `stripe listen --forward-to localhost:8000/api/v1/billing/webhook`.
4. Turn on the **Customer portal** in the Dashboard (Settings > Billing >
   Customer portal) so "Open Stripe billing portal" works.
5. Make sure `FRONTEND_URL` is the dashboard's public URL; Checkout returns there.
6. Pay with card `4242 4242 4242 4242`, any future date, any CVC.

Products are created in Stripe automatically on first checkout with ids
`cazo_easm_<plan>`; prices are sent with each checkout, so no Price ids are
needed.

## Pages

- `/pricing`: public plan comparison.
- `/billing`: current plan, usage meters, payment methods, invoices, cancel or
  resume renewal, link to the Stripe portal.
- `/billing/checkout`: choose plan, term, clients, extra domains and payment
  option, then go to Stripe.
- `/billing/success`: confirms the payment after Stripe redirects back.

## Data

Tables `billing_subscriptions` (one row per org), `billing_invoices` and
`billing_events` (processed webhook ids, for idempotency) are created by
`create_all` at startup. The older unused `subscriptions` / `invoices` tables
from Alembic revision `g0h1i2j3k4l5` are left alone.
