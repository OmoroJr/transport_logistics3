# Transport Logistics — Custom App for ERPNext 16

A custom Frappe app that adds Truck, Fuel, Tyre and Maintenance management to
ERPNext 16, for an owned-fleet transport operation, with a built-in
**Cost per Truck** analysis report.

## What's included

| DocType | Purpose |
|---|---|
| **Truck** | Master record: reg no, specs, current odometer, purchase cost, depreciation rate, insurance/license/inspection expiry dates |
| **Truck Fuel Log** | Every refuel: qty, rate, amount, odometer, auto-computed distance covered & km/litre efficiency |
| **Tyre** | Tyre master: serial, brand/size, purchase cost, lifetime km run, retread count, current truck/position |
| **Tyre Movement Log** | Fitted / Removed / Rotated / Retreaded / Scrapped events; drives the Tyre master's live state |
| **Truck Maintenance Log** | Scheduled service, repair, breakdown, inspection — parts + labour + other cost, downtime, next-service-due |
| **Truck Expense** | Insurance, licenses/permits, tolls, driver allowance, parking, fines, etc. |
| **Truck Trip** | Optional trip/haulage log with distance and revenue (for 3rd-party haulage income) |
| **Accident Report** | Full accident/incident record with cost, injuries, official reports, root cause |
| **Driver Safety Incident** | Violations, near misses, and other safety events, with points-based scoring |
| **Driver Mileage Payment** + **Driver Mileage Payment Route** | Pay drivers per destination/route driven (not per km) — Cash, M-Pesa, or Bank Transfer, with optional live M-Pesa B2C disbursement |
| **Route** | Master of standard routes (e.g. "Mombasa - Nairobi") with a flat per-trip driver rate |
| **Workshop Job Card** + **Workshop Job Card Item** | In-house garage work order: labour, spare parts (from ERPNext Stock), auto-issues stock, auto-creates the Truck Maintenance Log |
| **Trailer** | Trailer master — Tipper, Flatbed, Low Loader, Curtain Sider, Tanker, Skeletal, Reefer, or Other |
| **Trailer Coupling Log** | Records Coupled/Decoupled events; drives Trailer's live "current truck" status |
| **Gate Pass** | Yard/gate in-out log per truck (+ trailer), with purpose, cargo, seal number, security officer, and dwell-time |
| **Truck Utilization** (Script Report) | Active Days vs Downtime Days vs Idle Days per truck, and Utilization % |
| **Trailer Utilization** (Script Report) | Coupled Days vs Uncoupled Days per trailer, reconstructed from coupling history |
| **Transport Logistics Settings** | Single: GL posting accounts, compliance alert window, notify role, driver pay defaults, M-Pesa B2C credentials, workshop defaults |
| **Truck Cost Analysis** (Script Report) | Per-truck: distance run, fuel cost & efficiency, tyre cost, maintenance cost, accident cost, other expenses, prorated depreciation, **total cost, cost/km, revenue, profit/loss** — filterable by date range, truck, company |
| **Tyre Replacement Due** (Script Report) | Tyres past a configurable % of expected life, flagged Due Soon / Overdue |
| **Driver Safety Scorecard** (Script Report) | Per-driver safety score and rating from accidents + safety incidents |
| **Authority to Load** | Formal loading gate: verifies truck is empty + compliance docs valid before a trip can start |
| **Truck Fleet Status** (Script Report) | Live view of which trucks are Loaded/En Route vs Empty/Available |
| **Shipment** + **Shipment Charge** + **Shipment Document** | Clearing & forwarding job tracking: customs, charges, documents, client billing |
| **Fuel Tank** | Bulk fuel storage master, bridging to an ERPNext Warehouse + Item for live stock/valuation |
| **Bulk Fuel Purchase** | Records fuel delivered into a tank — creates a Stock Entry (Material Receipt) |
| **Fuel Dispensing** | Records fuel dispensed from a tank to a truck — creates a Stock Entry (Material Issue) + an auto Truck Fuel Log |
| **WhatsApp Message Log** | Audit trail of every outgoing/incoming WhatsApp message (Meta Cloud API), with delivery status |

Two custom roles are shipped as fixtures: **Transport Manager** (full rights)
and **Transport User** (data entry + view reports, no delete).

## How the numbers flow into the Cost Analysis report

For the selected date range and truck(s), the report pulls:

- **Distance** = max(odometer) − min(odometer) from submitted Fuel Logs in range
- **Fuel cost** = sum of `total_amount` from Fuel Logs in range
- **Tyre cost** = sum of `cost` on Tyre Movement Logs (retreads etc.) in range
- **Maintenance cost** = sum of `total_cost` from Maintenance Logs in range
- **Other expenses** = sum of `amount` from Truck Expense in range
- **Depreciation** = straight-line: `(purchase_cost − salvage_value) × rate% / 365 × days-in-range`
- **Revenue** = sum of `revenue` on Completed Truck Trips in range (0 if you don't haul for hire)
- **Total cost** = fuel + tyre + maintenance + other + depreciation
- **Cost per km** = total cost ÷ distance
- **Profit/Loss** = revenue − total cost

This gives you a true landed cost per truck, not just fuel — useful for
deciding when a truck is costing more than it's worth keeping.

## Installation on ERPNext 16 (bench)

Assumes you already have a working Frappe/ERPNext 16 bench.

```bash
# 1. From your bench directory, get the app
bench get-app transport_logistics /path/to/transport_logistics
# (or push this folder to your own git repo and use that URL instead)

# 2. Install it on your site
bench --site your-site.local install-app transport_logistics

# 3. Migrate to create the tables
bench --site your-site.local migrate

# 4. Build assets and restart
bench build --app transport_logistics
bench restart
```

If you're not using git yet, simply copy the `transport_logistics` folder
(the one containing `hooks.py`) into `apps/` inside your bench, add
`transport_logistics` to `apps.txt` and `sites/apps.json`, then run steps 3–4.

## After installing

1. **Assign roles** — give your fleet office staff the **Transport Manager**
   role, and drivers/clerks who only log data **Transport User**.
2. **Create Company** records already exist in ERPNext — link each Truck to
   the right one if you run multiple companies/branches.
3. **Create Truck records** first (one per vehicle), setting purchase cost,
   depreciation rate (default 20%/yr, adjust to your policy) and compliance
   expiry dates.
4. **Create Employee records** for drivers if not already in ERPNext, so they
   can be linked as "Assigned Driver".
5. Start logging **Truck Fuel Log** entries at every fill — mark `Full Tank`
   so efficiency (km/L) calculates correctly.
6. Log **Truck Maintenance Log** and **Truck Expense** as costs are incurred.
7. For tyres: create a **Tyre** record per physical tyre when bought, then use
   **Tyre Movement Log** (Fitted/Rotated/Retreaded/Removed/Scrapped) to track
   its life — the Tyre master updates itself automatically.
8. Open **Report → Truck Cost Analysis**, set a date range, and review cost
   per km per truck. Use the "Cost Analysis" button on any Truck form to jump
   straight there, filtered to that truck.

## New: Driver mileage payments (Cash / M-Pesa / Bank Transfer)

**Driver Mileage Payment** pays drivers **per destination/route driven**,
not per kilometer — that's a deliberate, corrected design: many transport
operations pay a flat rate per route (e.g. "Mombasa–Nairobi = KES X per
trip") rather than distance × rate, and this now matches that reality.

- First set up your **Route** master once — e.g. "Mombasa - Nairobi" with
  an Origin, Destination, and a flat **Driver Rate (per Trip)**. Reference
  distance is stored too, but it's informational only; pay is the flat rate.
- On a Driver Mileage Payment, add one row per route driven in the pay
  period, each with a **Route**, **No. of Trips**, and **Rate** (auto-filled
  from the Route, editable per payment if you want to override it for a
  specific case). A driver who ran two different routes in the same pay
  period just gets two rows — the child table supports as many as needed.
- **Fetch Trips for Period** button: pulls every Completed Truck Trip for
  that driver (with a Route set) in the From/To Date window, groups them by
  route, and fills in the trip counts automatically. You can still add or
  edit rows manually for trips that weren't logged as a Truck Trip.
- **Computed Amount** = sum of all route rows (rate × trips each). Add any
  **Other Allowance/Bonus** on top for **Total Amount Payable**.
- **Payment Method**: Cash, M-Pesa, or Bank Transfer.
  - For **Cash**/**Bank Transfer**: submitting the record marks it Paid.
  - For **M-Pesa**: the everyday path is to pay the driver via your M-Pesa
    app/till as usual, then type the **M-Pesa Transaction Code** in here and
    submit — marks it Paid, just like Cash.
- Quick-create buttons: **Truck → Create → New Mileage Payment**, and
  **Employee → Create → New Mileage Payment**.
- If GL posting is enabled, each payment debits a **Driver Payment Expense
  Account** and credits **Cash Account** or **M-Pesa Account** (configured
  in Transport Logistics Settings) depending on how it was paid.

To have Truck Trip auto-fill Origin/Destination and drive this, link a
**Route** on the Truck Trip itself — Origin/Destination fetch from the Route
if left blank, but stay manually editable for one-off trips with no
standard route.

### Optional: real M-Pesa B2C disbursement (advanced)

For operators who want to actually *send* the money from ERPNext rather
than pay manually and log the code, there's a working Safaricom **Daraja
B2C** integration (`mpesa.py`):

- An **"Initiate M-Pesa Payment"** button appears on unpaid M-Pesa records.
  It requests an OAuth token, then calls the B2C `paymentrequest` endpoint
  to send the amount straight to the driver's phone.
- Two whitelisted, guest-accessible endpoints receive Safaricom's async
  response and finish the job automatically:
  - Result URL: `.../api/method/transport_logistics.transport_logistics.mpesa.b2c_result_callback`
  - Queue Timeout URL: `.../api/method/transport_logistics.transport_logistics.mpesa.b2c_timeout_callback`
  On success, the callback fills in the real M-Pesa transaction code, marks
  the payment Paid, and submits it — triggering GL posting automatically.

**This needs real setup on Safaricom's side before it'll work**, which is
outside what any code can configure for you:
1. A Daraja app with **B2C API access** and Go-Live approval on your
   shortcode (sandbox works for testing without production approval).
2. A **Security Credential** — your initiator password encrypted with
   Safaricom's public certificate, generated via the Daraja portal.
3. Your site's callback URLs must be **real, publicly reachable HTTPS**
   endpoints (won't work on `localhost` or an internal-only server).

Fill all of this into **Transport Logistics Settings → M-Pesa B2C
Integration** and tick "Enable Live M-Pesa B2C Disbursement" only once
you've got it. Until then, leave it off and just log payments manually —
that path always works with zero setup.

## New: One truck per driver, one truck per trailer

Two business rules are now enforced at the database-validation level, not
just left to convention:

- **A driver can only be assigned to one Truck at a time.** Trying to set
  the same Employee as `Assigned Driver` on a second (non-Disposed) Truck
  throws an error naming the truck they're already on — unassign them there
  first.
- **A trailer can only be coupled to one Truck at a time, and a Truck can
  only have one trailer coupled at a time.** Trailer Coupling Log checks
  both directions: coupling a trailer that's already on another truck is
  blocked, and coupling a second trailer onto a truck that already has one
  is blocked too — either way, record a **Decoupled** entry first.
- The **Truck** list view now shows a **Currently Coupled Trailer** column
  directly, so you can see the pairing without opening each record (the
  **Trailer** list already showed its current truck the same way).

## New: Workshop module (in-house garage / job cards)

**Workshop Job Card** is the shop-floor work order — separate from, but
feeding into, the Truck Maintenance Log you already had:

- Complaint, diagnosis, work done, technician, labour hours × labour rate.
- A **Trailer** field (auto-filled from the truck's currently-coupled
  trailer, if any) so job cards on articulated combos record which trailer
  was attached during the work — it also gets folded into the auto-created
  Maintenance Log's description for traceability.
- A **Parts** table pulling from ERPNext's own **Item** master — add spare
  parts with qty and rate; cost totals automatically.
- Set an **Issue Parts From Warehouse** and, on submit, a **Stock Entry
  (Material Issue)** is created and submitted automatically to actually
  deduct the parts from stock. If there isn't enough stock, the Job Card
  still saves (cost is still tracked) and you get a warning to fix stock
  manually — it won't block you.
- On submit, the Job Card **automatically creates and submits a Truck
  Maintenance Log** carrying the same parts/labour/other cost — so every
  workshop job flows straight into **Truck Cost Analysis** and optional GL
  posting with zero extra work, using exactly the machinery you already
  have. The Job Card is the shop-floor detail; the Maintenance Log stays the
  single source of truth other reports read from.
- Quick-create: **Truck → Create → New Job Card**.

Defaults for **Default Workshop Warehouse** and **Default Labour Rate** live
in Transport Logistics Settings.

## New: Driver safety and accident reporting

| DocType | Purpose |
|---|---|
| **Accident Report** | Full incident record: truck, driver, date/time, severity (Minor/Moderate/Major/Fatal), type, location, description, third-party/injury/fatality flags, police report & insurance claim numbers, repair/other cost, insurance amount recovered, net cost, root cause, corrective action, photo attachment |
| **Driver Safety Incident** | Lighter-weight log for traffic violations, speeding, near misses, harsh braking/acceleration, fatigue, phone use, seatbelt violations etc. — with a severity-based points deduction |
| **Driver Safety Scorecard** (Script Report) | Per driver: accident count & at-fault count, safety incident count, total points deducted, accident cost, logged fines, a computed **Safety Score** (starts at 100, deducted per accident severity and per incident), and a **Good / Watch / Poor** rating |

**How the score is computed:** every driver starts at 100. Each submitted
Driver Safety Incident deducts its `points_deducted` (auto-defaulted from
severity: Low=2, Medium=5, High=10, editable). Each submitted Accident Report
deducts a fixed penalty by severity — Minor 5, Moderate 15, Major 30, Fatal
50. Score floors at 0. Rating: **Good** ≥85, **Watch** 60–84, **Poor** <60.

**Truck-level effects:**
- A Major or Fatal Accident Report automatically sets the Truck's status to
  *Under Maintenance* on submit — you clear it back to *Active* once it's
  inspected and cleared.
- Accident **net cost** (repair + other − insurance recovered) now feeds into
  the **Truck Cost Analysis** report as its own column, alongside fuel,
  tyres, maintenance, and depreciation — so a truck with a bad accident
  history shows up immediately in cost-per-km.
- If GL posting is enabled (see below), accidents post their net cost to a
  new **Accident/Repair Expense Account** you configure in Transport
  Logistics Settings.

**Note on fines:** Driver Safety Incident has an informational
`fine_amount` field for scoring purposes only — it does not post to the
ledger. If a fine is actually paid, log it separately as a **Truck Expense**
(type: Fine) so it's costed against the truck and optionally hits the GL.

**Immediate + scheduled alerting:** a Major/Fatal Accident Report, or a High
severity Driver Safety Incident, notifies the notify role **immediately on
submit** — you don't have to wait for the next scheduled run. The same daily
job also still runs for compliance-expiry checks (see below). Both share one
`notify_users()` helper in `tasks.py`, so behaviour (Notification Log + ToDo,
no duplicate spam) is consistent everywhere.

**Print format:** Accident Report ships with a ready-to-use **Accident
Report Print** format (set as default) — a clean single-page layout with
severity badge, all details, cost summary, and signature lines, suitable for
insurance filing or physical record-keeping. Open any Accident Report and
use Print (Ctrl/Cmd+P) as normal.

## New: Compliance expiry alerts

A daily scheduled job (`transport_logistics.transport_logistics.tasks.check_document_expiry`)
checks every active Truck's **Insurance, License, Inspection and COMESA/Yellow
Card** expiry dates. Anything expired, or expiring within the configured
window, raises:

- a **Notification Log** entry (shows in the bell icon) for every user with
  the notify role, and
- one **ToDo** assigned to the first such user, so it's trackable/closeable.

Configure this in **Transport Logistics Settings**:

| Field | Default | Purpose |
|---|---|---|
| Alert Days Before Expiry | 30 | How far ahead to start warning |
| Notify Role | Transport Manager | Who gets notified |

No extra setup needed — `bench --site your-site migrate` registers the
scheduler event automatically (make sure `bench` has the scheduler enabled:
`bench --site your-site enable-scheduler`).

## New: Posting costs to the General Ledger

Optional — off by default. Turn on **Transport Logistics Settings → Post
Costs to General Ledger** and fill in the accounts, and from then on every
**submitted** Truck Fuel Log, Truck Maintenance Log, Truck Expense, and Tyre
Retread (Tyre Movement Log) automatically creates and submits a matching
**Journal Entry**:

- Debit: the relevant expense account (Fuel / Maintenance / Tyre / Other)
- Credit: your configured Default Payment/Credit Account (Cash, Bank, or a
  Creditors account — your call)
- Cost Center: from the document, falling back to the settings' default

The Journal Entry name is stored back on the source document (`journal_entry`
field, read-only) so:
- postings never duplicate on re-save, and
- **cancelling** the source document automatically cancels its Journal Entry.

If you'd rather route these through Purchase Invoices against a Supplier
(e.g. to track amounts owed to a specific garage or fuel station) instead of
straight Journal Entries, that's a natural next iteration — say the word and
I'll swap the posting logic over.

## New: Tyre Replacement Due report

**Report → Tyre Replacement Due** lists every Fitted/In-Stock tyre whose
`total_km_run ÷ expected_life_km` is above a threshold (default 80%), with:

- **Due Soon** (80–99% of expected life used)
- **Overdue** (100%+)

Filterable by truck, tyre status, and the threshold percentage. A bar chart
of % life used per tyre renders above the table.

**Tip:** to get this as a dashboard "Number Card" (e.g. a red count tile on
your ERPNext home dashboard), go to **Number Card → New**, set "Report" as
the source, pick **Tyre Replacement Due**, and set the aggregate function to
Count. Takes about a minute in the UI and I didn't want to hand-craft that
JSON blind without you able to see it render first.

## New: Trailers, gate pass, and utilization reporting

Some trucks in your fleet are rigid units; others are truck-tractors that
pull a separate trailer (tipper, flatbed, low loader, etc.). This models
that properly rather than treating a truck+trailer combo as one vehicle:

- **Trailer** is its own master — type (Tipper/Flatbed/Low Loader/Curtain
  Sider/Tanker/Skeletal/Reefer/Other), registration, capacity, axle count,
  purchase cost, insurance/inspection expiry.
- **Trailer Coupling Log** records when a trailer is **Coupled** to or
  **Decoupled** from a specific truck. This keeps `Trailer.current_truck`
  and `Truck.current_trailer` in sync automatically — check either record
  and you'll see the current pairing. History of every past pairing is kept
  for the utilization report to reconstruct later.
- **Gate Pass** logs entries and exits at your yard/gate for both **Vehicle**
  and **Pedestrian** traffic (a single `Pass Type` field switches the form):
  - **Vehicle**: truck (and its currently-coupled trailer, auto-filled),
    driver, cargo description, seal number, odometer at gate-out.
  - **Pedestrian**: visitor name, ID/passport number, phone number, and
    who/which department they're visiting — for foot traffic like
    contractors, interviewees, or official visitors who aren't arriving in
    a company vehicle.
  - Both share: purpose, gate in/out time, security officer on duty, and a
    one-click **Gate Out** button that stamps the exit time and calculates
    time-on-site automatically.

### Truck Utilization report

For each truck over a date range:

- **Active Days** — distinct days with a Completed Truck Trip or a Departed
  Gate Pass (i.e. days it actually did something)
- **Downtime Days** — `Truck Maintenance Log.downtime_hours` in the period,
  converted to days
- **Idle Days** — whatever's left: Total Days − Active Days − Downtime Days
- **Utilization %** — Active Days ÷ Total Days
- Plus Distance Run and Avg Km per Active Day, so you can see which trucks
  are both idle *and* underperforming when they do move

This is a deliberately simple, explainable definition rather than a
time-in-motion/telematics metric — Truck Trip currently records a trip date,
not start/end times, so "day-level activity" is what the data actually
supports. It's enough to flag a truck sitting idle for weeks, which is
usually the real question being asked.

### Trailer Utilization report

Same idea for trailers: reconstructs Coupled→Decoupled intervals from
**Trailer Coupling Log** history (an unmatched final "Coupled" is treated as
still ongoing through the report's end date), and reports **Coupled Days**
vs **Uncoupled Days** vs **Utilization %** per trailer — useful for
spotting an expensive low loader that's spent most of the quarter sitting
in the yard uncoupled.

## New: Truck loading/offloading, Authority to Load, and fleet availability

A truck can't just be marked "used" again the moment it drops off cargo —
in real operations it needs to actually be at the client, unloaded, and
confirmed before it's available for its next job. This models that:

- **Truck Trip** now has an `Offload Status` (Not Offloaded / Offloaded).
  A truck can't start a new trip while it has another **Ongoing** trip that
  hasn't been offloaded yet — trying throws an error naming the trip it's
  still on.
- **Offload at Client** button (on an Ongoing trip) records the odometer
  reading and who confirmed it, marks that trip **Completed**, and frees the
  truck up — this is the single mechanism that both completes the trip and
  makes the truck available again, exactly as requested.
- **Truck Fleet Status** report shows every truck's live state — **Loaded —
  En Route to Client** (with which trip, customer, and destination) or
  **Empty — Available** — the "trucks going to clients vs empty trucks
  coming from clients" view. Deliberately computed live from Truck Trip
  records rather than stored as a separate field on Truck, so it can never
  drift out of sync with the actual availability check.

### Authority to Load — the loading gate

Before a truck can actually start a loaded trip, someone has to formally
authorize it. **Authority to Load**:

- Is created against a specific **Planned** Truck Trip (the "Request
  Authority to Load" button on a Planned trip pre-fills this).
- On save, automatically checks: the truck is currently empty (not already
  loaded on another trip), and that Insurance, License, Inspection, and
  COMESA/Yellow Card expiry dates are all still valid as of today. A blank
  expiry date is treated as "not tracked" rather than a failure, so it
  doesn't punish fleets that haven't filled in every date field.
- **Cannot be submitted if any check fails** — the failure reasons are
  listed right on the form.
- A Truck Trip **cannot move to Ongoing** (i.e. the truck can't actually be
  loaded) without a submitted Authority to Load on file for that specific
  trip — so this is a hard gate, not just an advisory checklist. Each trip
  needs its own fresh Authority to Load; an old one doesn't carry over.

### Revenue from Sales Order, or entered manually

Truck Trip's **Revenue Earned** now auto-fills from a linked **Sales
Order**'s Grand Total if you pick one (filtered to the trip's customer) —
or just type it in directly if there's no Sales Order for this haulage.
Changing the customer clears a mismatched Sales Order automatically.

## New: Clearing & forwarding

**Shipment** tracks an import/export/transit clearing job end-to-end:

- Client, shipment type, mode of transport (Sea/Air/Road/Rail), status
  (Booked → Documents Received → Customs Entry Filed → Customs Released →
  In Transit → Delivered → Completed), assigned clearing agent, and the
  truck assigned for the last-mile delivery leg.
- Transport details: Bill of Lading/AWB, vessel/flight, container number,
  ports of loading/discharge, ETA/ATA.
- Customs: entry number (IDF/Entry), release date.
- A **Charges** table — Customs Duty, Port Charges, Demurrage, Storage,
  Clearing Fee, Transport, Documentation, Insurance, Other — each flagged
  Billable to Client or not, and Payable By Client (recoverable) vs Company
  (own cost). Totals compute automatically.
- A **Documents** checklist — Bill of Lading, Commercial Invoice, Packing
  List, Certificate of Origin, IDF, Certificate of Conformity, Customs
  Entry, Release Order, Delivery Note — each trackable as Pending/Received
  with an attachment.
- **Create Sales Invoice** button generates a draft Sales Invoice for the
  client from all billable charges in one click. This needs a service Item
  with "Clearing" and "Forwarding" in its name created once (e.g. "Clearing
  & Forwarding Services") — the button tells you if it can't find one.

## New: Bulk fuel purchase and dispensing from your own pumps

For fleets that buy diesel/petrol in bulk and dispense it themselves rather
than fueling at stations:

- **Fuel Tank** is a lightweight master that bridges to ERPNext's own Stock
  module — link it to a **Warehouse** (create one per physical tank) and a
  stock **Item** representing the fuel (e.g. "Diesel - Bulk", in Litres).
  Opening a Fuel Tank shows live stock level and average cost per litre,
  with a simple capacity bar — always live, never a stale stored number.
- **Bulk Fuel Purchase** records a delivery into the tank: quantity, rate,
  supplier, invoice number. On submit it creates a **Stock Entry (Material
  Receipt)** into the tank's warehouse — so ERPNext's own stock ledger
  handles quantity and moving-average valuation; nothing here reinvents
  that math.
- **Fuel Dispensing** is how a truck actually gets fueled from your own
  pump: pick the tank and truck, enter litres and odometer reading. On
  submit it:
  1. Creates a **Stock Entry (Material Issue)** from the tank, valued
     automatically at the tank's current moving-average cost.
  2. **Auto-creates a submitted Truck Fuel Log** with that same quantity,
     rate, and odometer reading — tagged `Source: Internal Bulk Dispensing`
     — so it flows into Truck Cost Analysis, the Dashboard, fuel efficiency,
     everything, exactly like an externally-purchased fill-up. Truck Fuel
     Log stays the single source of truth for fuel cost regardless of where
     the fuel came from.
  3. Blocks with a clear error if the tank doesn't have enough stock,
     rather than letting it go negative silently.

**Accounting note on GL posting (optional, off by default):** bulk fuel
bought into a tank is a stock asset, not yet an expense — it only becomes
an expense when dispensed into a truck. So if you enable GL posting, Bulk
Fuel Purchase debits a **Fuel Stock Asset Account** (new setting) and Fuel
Dispensing debits **Fuel Expense** / credits that same asset account — the
existing Truck Fuel Log GL hook is automatically skipped for internally-
dispensed logs so the expense isn't posted twice.

**⚠️ If your Company already has Perpetual Inventory accounting enabled for
the fuel Item**, ERPNext's own Stock Entries will already be posting GL
entries for these stock movements — do **not** also enable this app's GL
posting for Bulk Fuel Purchase/Fuel Dispensing in that case, or costs will
be double-counted. Pick one: ERPNext's native stock accounting, or this
app's simplified Journal Entry approach — not both.

## New: Truck Cost Dashboard page (custom visual dashboard)

A dedicated, purpose-built dashboard page — **Truck Cost Dashboard** in the
workspace, or the **Cost Dashboard (this truck)** button on any Truck —
gives a single-truck-or-fleet-wide visual view: KPI cards across the top
(Total Distance, Fuel/Maintenance/Tyre/Other/Depreciation Cost, Total Cost),
a cost-breakdown donut with a percentage legend, a performance summary panel
(fuel efficiency, cost/km, revenue, profit/loss, profit/km), and a trailing
6-month cost-vs-revenue trend line chart.

Filter by Truck (leave blank for the whole fleet) and a date range at the
top — the KPI cards and breakdown reflect exactly that range, while the
trend chart always shows the trailing 6 months for historical context
regardless of the selected range (matching how a "trend" panel is normally
expected to behave — a single month selected up top doesn't make the trend
line pointless).

**Now upgraded to use Chart.js and Font Awesome via CDN**, since you're
connecting this server to the internet:
- The donut chart renders with **Chart.js** (loaded from cdnjs) — smoother,
  proper hover tooltips showing exact amounts, real doughnut cutout styling.
- KPI card icons use **Font Awesome 6** (also from cdnjs) instead of emoji.
- **Graceful degrade kept intentionally**: if Chart.js hasn't finished
  loading yet (or the connection drops), the page automatically falls back
  to the original pure-CSS `conic-gradient` donut — nothing breaks, it just
  looks slightly plainer until Chart.js loads. The trend line still uses
  `frappe.Chart` (bundled with Frappe, no CDN needed) — only the donut and
  icons needed the extra polish. I verified both the Chart.js path and the
  fallback path actually execute correctly by running the real page code
  against a mock DOM twice — once simulating Chart.js loaded, once
  simulating it unavailable — rather than assuming the fallback works.
- CDN URLs used (verified live via search before shipping, not guessed):
  `cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.0/chart.umd.min.js` and
  `cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css`.

The numbers come from the exact same helper functions as the **Truck Cost
Analysis** report (imported directly, not re-implemented) — so the
dashboard and the report can never quietly disagree with each other.

### Click any KPI card to see what's behind the number

Every KPI card (Total Distance, Fuel Cost, Maintenance Cost, Tyre Cost,
Other Expenses, Depreciation, Total Cost) is clickable — it opens a dialog
listing the actual underlying records that sum to that figure, not just the
static total:

- **Fuel Cost** → every Truck Fuel Log entry in the period (date, qty, rate,
  amount, station, efficiency)
- **Maintenance Cost** → every Truck Maintenance Log entry (type, vendor,
  parts/labour/other cost breakdown)
- **Tyre Cost** → every cost-bearing Tyre Movement Log entry (retreads)
- **Other Expenses** → every Truck Expense entry (type, reference, amount)
- **Depreciation** → the actual calculation per truck (purchase cost, rate,
  salvage value, days in period, resulting depreciation) — there's no
  single source document for this one since it's computed, so the dialog
  shows the computation itself instead
- **Total Cost** → the same category breakdown as the donut, as a table
- **Total Distance** → every Completed Truck Trip in the period with its
  route and distance, since that's the more actionable "components" view
  than raw odometer numbers

A **View Full List** button on the dialog (where applicable) jumps straight
to that doctype's list view, filtered to the truck you're looking at.

### Total Distance showing blank/zero — fixed

This was a real bug, not just missing data: distance was calculated purely
from Truck Fuel Log odometer readings (min/max in range). If your fleet logs
trips but doesn't log fuel fill-ups with odometer readings for a given
period, that returned 0 even though real distance data existed elsewhere.
Distance is now the **larger of** the fuel-log-based figure and the sum of
Truck Trip distances in the period — so it reflects whichever logging habit
your team actually uses, rather than assuming everyone fills in the same
field.

I confirmed this fix, and the whole drill-down click flow, by actually
executing the dashboard's JavaScript against a mock DOM with sample data —
clicking a simulated "Fuel Cost" card, verifying it called the backend with
the right arguments, and verifying the resulting dialog actually contained
the sample row data — not just checking that the code parses.

I tested the actual page JavaScript by executing it (not just checking
syntax) against a mock DOM/Frappe environment with sample data before
shipping it, to catch real rendering bugs rather than just parse errors.

## New: Fleet Dashboard (charts and number cards)

A native ERPNext **Dashboard** page — *Dashboards → Transport Logistics*, or
the **Fleet Dashboard** button on any Truck — brings together:

**Number cards** (single-figure tiles):
- Active Trucks, Trucks Under Maintenance, Trucks In Yard, Active Trailers,
  Open Job Cards, Unpaid Driver Payments

**Charts:**
- **Fleet Status** — donut of trucks by status (Active/Under Maintenance/
  Idle/Disposed)
- **Trailer Fleet by Type** — pie of trailers by type (Tipper/Flatbed/Low
  Loader/etc.)
- **Fuel Cost Trend** — monthly line chart, last 12 months
- **Truck Trips Over Time** — monthly bar chart of completed trips
- **Maintenance Cost Trend** — monthly line chart, last 12 months
- **Accidents by Severity** — bar chart, all-time
- **Tyre Status Overview** — donut of tyres by status

The five most relevant cards and charts (Active Trucks, Trucks Under
Maintenance, Trucks In Yard, Open Job Cards, Unpaid Driver Payments; Fleet
Status, Trailer Fleet by Type, Fuel Cost Trend, Maintenance Cost Trend,
Accidents by Severity) are **also embedded directly on the Transport
Logistics workspace tile itself**, so the moment you open the module you see
live numbers and graphs — not just a menu of doctypes. The full set of seven
charts and six cards lives on the standalone Dashboard page for a more
complete view.

Every chart and number card is a normal editable ERPNext record — open any
of them (Dashboard Chart list / Number Card list) to change the color,
timespan, chart type (bar/line/donut/pie), or filters to match how you
actually want to slice it. Nothing here is hardcoded into the app's code.

## New: WhatsApp notifications (Meta Cloud API)

Optional integration with Meta's official WhatsApp Business Cloud API
(`transport_logistics/whatsapp.py`), covering three independently-toggled
channels — set up under **Transport Logistics Settings → WhatsApp
Integration**:

| Channel | Sent to | Sent when |
|---|---|---|
| **Internal alerts** | Every enabled user holding the Notify Role (via their User → Mobile No) | Same trigger points as the existing Notification Log/ToDo — Highway Breakdown, Major/Fatal Accident Report, High-severity Driver Safety Incident, and the daily compliance/document expiry check |
| **Driver-facing** | The driver's Employee → Cell Number | Authority to Load submitted (cleared to load), Truck Trip dispatched (Planned → Ongoing), Truck Fuel Log submitted (fuel confirmation) |
| **Customer-facing** | Shipment → Client WhatsApp Number (auto-filled from the client's primary Contact if on file) | Shipment status reaches Customs Released, In Transit, Delivered, or Completed |

### Setup

1. Create a Meta Business + WhatsApp Business Platform app at
   [business.facebook.com](https://business.facebook.com), with a
   registered phone number.
2. On **Transport Logistics Settings**, turn on **Enable WhatsApp
   Integration** and fill in:
   - **Phone Number ID** (from the Cloud API dashboard)
   - **Access Token** — use a **permanent** token from a System User /
     Business integration, not the default 24-hour test token
   - **Default Country Code** — for turning locally-entered numbers like
     `0712345678` into `254712345678`
3. Tick whichever of the three **Notification Channels** you want live.
4. Save, then use **Send Test Message** (toolbar button, once a **Test
   Number** is filled in) to confirm it's working.
5. Optional: to receive delivery-status updates and inbound replies,
   register a webhook in Meta App settings pointing at
   `https://your-site/api/method/transport_logistics.transport_logistics.whatsapp.webhook`,
   with the **Webhook Verify Token** you set in Settings.

Every send is logged to **WhatsApp Message Log** (Sent/Failed/Delivered/Read,
with the error message on failure) — sending is always best-effort and never
blocks the document that triggered it. Outside Meta's 24-hour customer
session window, freeform text only reaches numbers that messaged your
business number first; `send_whatsapp_template()` in `whatsapp.py` is there
for sending pre-approved Message Templates to reach anyone regardless of
window.

## Suggested next steps (not built yet)

- Route GL postings through Purchase Invoice + Supplier instead of plain
  Journal Entries, if you want payables tracked per vendor/fuel station.
- A Truck Trip → Delivery Note/Sales Invoice link if you invoice haulage
  customers directly from ERPNext.
- Email (not just in-app notification) for expiry alerts — straightforward
  to add via `frappe.sendmail()` in `tasks.py` if you want it.
- Inbound WhatsApp conversation handling (e.g. a driver replying "CONFIRM")
  — the webhook already logs incoming messages to WhatsApp Message Log;
  acting on them is the natural next layer.

Happy to build any of the above — just say which one.
