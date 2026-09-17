# Odex Road Mechanic (core)

Directory plus roadside assistance, vehicle recovery and the spare / used parts
marketplace. Version 18.0.2.0.0. Install the optional
`odex_road_mechanic_booking` addon on top for appointments and quotations.

Workshop directory for Odoo 18 **Community** — branded as **ROAD MECHANIC / UAE AUTO SOLUTIONS**.

The addon renders directory content only. The standard Odoo website header and
footer stay in place and keep controlling the logo, menus and footer links. All
custom CSS is scoped under `.odex-road-mechanic`.

## Install

The module installs cleanly on a database that already contains Road Mechanic
master data. A `pre_init_hook` runs before the data files load and adopts any
existing vehicle brand, service or workshop type with a matching name, so the
loader updates those rows instead of trying to insert duplicates. That is what
previously stopped an install with
`duplicate key value violates unique constraint ..._name_uniq`.

1. Copy `odex_road_mechanic` into your addons path, e.g.
   `/opt/odoo18/wms25ii/custom-addons/`.
2. Restart the Odoo service (Python models require a full process restart).
3. Apps → Update Apps List → search "Road Mechanic" → Install.

Dependencies: `base`, `mail`, `portal`, `website`. No Enterprise modules.

## Configure

* **Settings → Website → Road Mechanic Directory**
  * *Road Mechanic as Homepage* — serve the directory on `/` instead of the
    standard website homepage. Off by default; the directory always lives at
    `/road-mechanic`.
  * *Workshops per Page* — pagination size (default 12).
  * *Directory Hero Image* — hero background. Upload your own workshop photo
    here; a subtle branded placeholder is used when it is empty.
  * *Hero Overlay Darkness* — 0 to 95. How much the photo is darkened behind
    the heading so the white text stays readable. Default 70.
  * *Phone / WhatsApp / Email* — shown on `/contact`.
* **Road Mechanic → Configuration** — services, workshop types, vehicle brands
  and UAE locations. Master data is preloaded (8 types, 14 services, 26 brands,
  41 areas across the 7 emirates).
* If you change the CSS/JS during development, clear the asset bundles
  (Settings → Technical → Assets, or restart with `--dev=all`).

## Roles

| Role | Group | Scope |
|---|---|---|
| Admin | `Road Mechanic Admin` | Everything: verify, reject, publish, feature, priority, moderation |
| Staff | `Road Mechanic Staff` | Internal user: edit content, moderate reviews, handle inquiries. Cannot verify, publish, feature or rank |
| Garage Partner | `Garage Partner` (portal) | Own workshop only: content, photos, services, brands, hours. Sees own reviews and inquiries |
| Customer / Vehicle Owner | `Customer / Vehicle Owner` (portal) | Own inquiries and reviews |
| Public | — | Browse published workshops, search, register a workshop, send inquiries and reviews |

Verification, `is_verified`, `verified_by`, `verification_date`,
`verification_status`, `is_featured`, `priority` and `website_published` are
blocked at ORM level for anyone except an Admin (or an internal, explicitly
sudo-ed business transition such as "Submit for verification").

## Admin workflow

1. A workshop registers on `/register-workshop` → record created with
   status **Submitted**, unpublished, not verified.
2. Road Mechanic → Workshops → Pending Verification → open the record.
3. *Start Review* → check the trade licence (Verification tab, staff only) →
   *Verify* or *Reject* (rejection asks for a reason and can unpublish).
4. *Publish* to make the listing public. Optionally set *Featured* and
   *Listing Priority*.
5. Reviews arrive as **Pending** under Road Mechanic → Reviews and only affect
   the workshop rating once approved.
6. Inquiries arrive as **New** under Road Mechanic → Inquiries, with a smart
   button on each workshop form.

## Website routes

| Route | Purpose |
|---|---|
| `/road-mechanic` | Directory homepage (hero search, categories, verified, featured, all) |
| `/` | Same homepage when "Road Mechanic as Homepage" is enabled |
| `/workshops`, `/workshops/page/<n>` | Listing with filters, sort, grid/list, pagination |
| `/workshop/<slug>` | Workshop detail (gallery, services, brands, hours, reviews, inquiry, map, related) |
| `/services`, `/service/<slug>` | Service index and per-service listing |
| `/area/<slug>` | Per-area listing |
| `/about`, `/contact` | Content pages |
| `/register-workshop` | Public registration (+ `/register-workshop/submit`) |
| `/road-mechanic/inquiry`, `/road-mechanic/review` | Form endpoints (POST, CSRF protected) |
| `/road-mechanic/suggest` | JSON suggestions for the hero search field |
| `/my/workshops`, `/my/workshop/<id>` | Garage Partner portal |

## Ranking

`_order` is `is_verified desc, priority desc, is_featured desc, rating desc,
review_count desc, name asc`, so ordering happens in PostgreSQL. Listing pages
search with domains, count with `search_count` and page with `limit/offset` —
no full table loads into Python.

## Theme

Light and dark are both designed (not inverted). The toggle writes
`data-orm-theme` on `<html>` and stores the choice in `localStorage`; the first
visit follows `prefers-color-scheme`. All colours come from CSS variables
defined on `.odex-road-mechanic`.

## Known limitations

* Maps use OpenStreetMap embeds plus Google Maps links for directions. No API
  key is required and none is hardcoded. Latitude/longitude must be filled for
  the embedded map; otherwise only the address links are shown.
* Photo reordering in the portal is not implemented (add and remove are).
  Sequencing is available in the backend gallery.
* Duplicate-review protection is per partner (authenticated) and per email
  within 24h (anonymous). It is a deterrent, not a captcha.
* The hero uses a branded placeholder image. Upload a real workshop photo in
  Website settings for the intended look.
* No demo workshops are shipped, so the homepage sections stay empty until you
  create and publish workshops.


---

# Assistance, Recovery & Parts Marketplace

Third module of the Road Mechanic platform. Odoo 18 Community.

Install order: `odex_road_mechanic` → `odex_road_mechanic_booking` → this one.
Installing this module pulls the other two in automatically.

## The request-and-offer model

Customers never browse a parts catalogue. They post what they need; the platform
notifies every workshop whose listing declares the matching capability
(`Platform Services` tab: roadside, recovery, spare parts, used parts).
Suppliers answer with price, brand, condition, warranty, delivery and photos of
the actual part. The customer compares offers side by side, chats, then accepts
one — which rejects the others and assigns that supplier to the request.

## Routes

**Customer:** `/roadside-assistance`, `/recovery`, `/spare-parts`, `/used-parts`,
`/my-requests`, `/request/<id>`, `/offers/<id>`, `/chat/<id>`, `/my/notifications`

**Provider / supplier:** `/my/provider/requests`, `/my/provider/request/<id>`
(accept a job, move the status, send or update an offer, chat)

**Backend:** Road Mechanic → Service Requests (All / Roadside / Recovery /
Spare Parts / Used Parts), Supplier Offers, Notifications.

## Form UX

Each page is a 4-step form with a progress bar, per-step validation and values
kept while moving between steps: service choice → location or part → details and
photos → contact. Location uses the browser GPS with a map preview and manual
entry as fallback. Photo upload supports drag and drop, multi-select, previews
and mobile camera, capped at 8 images of 6 MB each, JPG/PNG/WEBP only.

## Privacy

Customer contact details are only shown to a provider once they are assigned or
their offer is accepted. Draft offers are invisible to customers by record rule.
Requests are visible to their own customer, to the providers that can serve that
request type, and to Road Mechanic staff.

## Known limitations

* Notifications are in-app (portal page plus counters). No email or push.
* Maps are OpenStreetMap embeds plus Google Maps links: no API key needed, and
  reverse geocoding is not performed, so the typed address is what providers see.
* Live tracking of a recovery truck on a map is not implemented; the status
  timeline is the tracking.
* No payment or escrow on accepted offers.
* Suppliers are notified through the in-app notification list, not by SMS.

---

# Shared primitives

Customer vehicles (`odex.road.mechanic.vehicle`) and the chat thread
(`odex.road.mechanic.message`) live in this module so both the marketplace and
the optional booking addon reuse them. The booking addon extends them rather
than redefining them.


---

# Workshop offers

Each workshop owns its promotions (`odex.road.mechanic.offer`). An offer always
carries a `workshop_id` and every public query filters on it, so an offer can
never surface on another workshop's page.

* **Types**: percentage, fixed amount, special price, free service. The badge
  ("10% OFF", "FREE") is derived from the type and value.
* **Validity**: start and end dates, end never before start. A daily cron
  deactivates offers a day after they expire, and every public query already
  excludes expired ones, so nothing stale is ever served.
* **Ranking on the homepage**: featured first, then priority, then newest.
  Featured and priority are admin-only; a Garage Partner cannot promote itself.
* **Where they appear**: homepage strip, `/offers`, the workshop page
  ("Offers from this workshop"), `/offer/<slug>` detail page, and a small badge
  on workshop cards when a promotion is running.
* **Garage Partner management**: `/my/workshop/<id>/offers` — create, edit,
  publish, delete, with image and gallery upload.
* **Admin**: Road Mechanic → Offers (All / Running / Expired) with filters for
  active, expired, featured, draft, published, workshop, service and dates.
* **Book this offer**: when the booking addon is installed, the offer page shows
  "Book this offer" and pre-fills the workshop and service on the booking form.

# Exact workshop location

Directions use the stored coordinates only — never the area or the street text,
which is what previously sent customers to the middle of Al Quoz.

* `latitude` / `longitude` at 7 decimal places (about 1 cm of precision).
* `has_exact_location` is computed and stored; "Get exact directions" only
  renders when it is true, and the embedded map is centred on the pin at a tight
  zoom rather than on an area centroid.
* `location_warning` shows an amber banner in the backend when coordinates are
  missing, and a second warning when they fall outside the UAE bounding box.
* Garage Partners set the pin at `/my/workshop/<id>/location` by dragging a
  marker on an OpenStreetMap layer (Leaflet from CDN, no API key, no billing),
  with "use my current location" and manual coordinate entry as fallbacks. The
  postal address is kept alongside but is never used for navigation.

# Customer pages

`/my/inquiries` and `/my/reviews` are separate pages, both linked from the
portal home. Inquiries show workshop, vehicle, service, date, status and last
update; statuses include "Quotation Received", set automatically when a garage
sends a quotation. Reviews show the rating, the text, the date and the approval
status, and can be edited by their author — which sends them back through
moderation. A customer can only ever see and edit their own records.


---

# Workshop detail page (redesigned)

The page is a premium marketplace layout built on the same models, routes and
forms as before — nothing in the backend changed, and the standard Odoo website
header and footer still wrap it. All styles are scoped to
`.roadmechanic-workshop-page`.

Structure: full-bleed hero (cover or main image, scrim, verified badge, name,
live rating, location, open/closed, service chips, best running offer badge) →
gallery strip with the existing lightbox → sticky section tabs → 70/30 content
and sidebar.

* **Tabs** (About, Offers, Services, Vehicle Brands, Working Hours, Reviews,
  Inquiry) scroll smoothly, track the scroll position and auto-centre on mobile.
* **About** clamps a long description behind "Read more" and shows a second
  image beside it on desktop.
* **Offers** shows only `workshop_id == this workshop`, running and published.
* **Services** and **Vehicle Brands** render from the workshop's own records,
  with the service icon and the brand logo when one is uploaded.
* **Working hours** come from `working_hours_rows()`. The directory returns the
  single opening/closing window; the booking addon overrides the method with the
  real per-day schedule, so the template never has to know which addons exist.
  Today's row is highlighted and the Open now / Closed flag is computed live.
* **Exact location** embeds the pin coordinates; "Get exact directions" only
  appears when `has_exact_location` is true.
* **One action bar only.** Book now, Send inquiry, WhatsApp and Call appear
  once, directly under the hero. They are deliberately absent from the sidebar.
  On mobile that bar is hidden and the sticky bottom bar (Call / WhatsApp /
  Book) takes over, so the actions never appear twice on one screen.
* **Get Directions appears once**, inside the Exact Location card in the
  sidebar, and only when `has_exact_location` is true.
* **Sidebar is informational**: logo, name, status flags, rating, phone,
  WhatsApp, email and address as plain text, the week's hours with a live
  Open now / Closed flag, the exact-location map, the verification note and a
  one-line offers summary linking to the single offers section.
* **Status vs class.** `workshop_class` (Class A / B / C) is the size and
  capacity category; verified and featured are platform statuses. They are
  separate fields and render as separate badges. Class, featured, verification,
  priority and publication are all manager-only at ORM level — a Garage Partner
  cannot raise its own class.
* Reviews, the review form, the inquiry form, ratings input, lightbox and mobile
  bar all keep their original ids and data attributes, so the existing
  JavaScript widgets and POST routes work untouched.


---

# Release 18.0.3.0.0

* **Listing type** on every company: Workshop, Spare Parts Supplier, Used Parts
  Dealer, Roadside Assistance or Recovery. The directory at `/workshops` lists
  workshops only; the other types appear on their own service page. The
  registration form asks for it up front, plus optional extra capabilities.
* **Provider directory** on `/roadside-assistance`, `/recovery`, `/spare-parts`
  and `/used-parts`: the registered companies for that service, searchable by
  name and area, each linking to its page for a call, WhatsApp or inquiry. The
  request-and-offer form stays above it.
* **Opening days** moved into the directory module. A workshop sets the days it
  opens and the hours per day, in the backend (Working Hours tab) or in the
  portal at `/my/workshop/<id>/hours`. Only the days actually configured are
  shown to customers, and Open now follows them. The booking addon now cuts its
  slots from these same days.
* **Brand logos from Fleet**: a vehicle brand uses its own logo, else the image
  of the Fleet brand with the same name when the Fleet app is installed. A
  button on the brand list imports them in bulk.
* **Brand colours in Settings**: primary, accent, verified, and the light and
  dark backgrounds and panels. They are injected as CSS variable overrides, so
  no code edit and no asset rebuild is needed.
* Hero photo is no longer washed out - the scrim only darkens where the text
  sits - and the logo sits next to the workshop name.
* The review form is collapsed behind a "Write a review" button and opens on
  click, or automatically when a submission comes back with an error.
* Empty states are written for their context: no workshop for a service, none
  in an area, no company for a platform service, and a different message when a
  search returned nothing.


---

# Release 18.0.3.1.0

* **Fixed the 403 on workshop pages.** The page reads the opening days, and the
  public group had no access to that model after it moved into the directory.
  Public, portal and internal users can now read the opening days of published
  workshops; editing is still limited to the owner and the Road Mechanic team.
* `/roadside-assistance`, `/recovery` and `/used-parts` are gone. Assistance and
  recovery are now requested from a company: any listing that offers them shows
  an **Assistance** or **Recovery** button, which opens a request form already
  targeted at that company, with the provider assigned on submission.
* **Registration** asks one question - Workshop or Spare Parts Supplier - plus
  two tick boxes for roadside assistance and recovery, and, for suppliers, a
  delivery question with a free-text detail line.
* **`/spare-parts` is now a directory** built like the workshop directory:
  search, area filter, delivers-parts and verified-only filters, pagination, and
  the same company cards. The post-a-request marketplace moved to
  `/spare-parts/request`.
* The workshop directory lists workshops only; suppliers appear in the spare
  parts directory.
* Delivery shows as a green line on the card and on the company page.


---

# Release 18.0.3.2.0 - spare parts categories

Categories are to a spare parts supplier what services are to a workshop: a
master model an administrator manages, not a hardcoded list.

* Model `odex.road.mechanic.part.category` with name, icon, description, image,
  sequence, slug, active and "show in directory". Add, rename or retire any of
  them from **Road Mechanic - Spare Parts Categories**; new ones appear on the
  website with no code change.
* Ships with Engine, Transmission, Exterior Body, Interior Parts, Suspension,
  Steering, Brake System, Electrical & Lights, AC & Cooling, Fuel & Exhaust and
  Filters.
* A supplier picks its categories at registration, and the Road Mechanic team
  can adjust them on the workshop form (the field replaces Services when the
  listing is a spare parts supplier).
* `/spare-parts` gains a category strip that filters the directory, the same way
  the service strip works on the workshop directory.
* Supplier cards list their categories where a workshop card lists services, and
  the company page shows a "Parts we supply" section with the delivery note.
* A parts request can name a category. When it does, the request is sent first
  to suppliers of that category, and only falls back to every supplier when none
  carry it.


---

# Release 18.0.4.0.0 - home page for the whole platform

The home page now represents all four categories instead of workshops alone,
in exactly eight sections, reusing the existing cards, rows, routes and theme
tokens - no new component or duplicate query.

Hero: "Find automotive services near you", with the existing search bar
untouched, and a quick-category strip for Workshops, Spare Parts, Roadside
Assistance, Recovery, Request a part and Services.

1. **Verified workshops** - one row, up to 6, to `/workshops?verified=1`
2. **Verified spare parts** - one row, to `/spare-parts?verified=1`
3. **All workshops** - the main listing rows, to `/workshops`
4. **Spare parts** - the main listing rows, to `/spare-parts`
5. **Roadside assistance** - providers row, to `/roadside-assistance`
6. **Recovery & pickup** - providers row, to `/recovery`
7. **Workshop offers** - offers row, to `/offers?listing=workshop`
8. **Spare parts offers** - offers row, to `/offers?listing=spare_parts`

* `/roadside-assistance` and `/recovery` are back, this time as **provider
  directories** with search and area filter. Requests still start from one
  company, so they land in that company's queue.
* `/offers` gained workshop / spare parts tabs, filtered on the listing type of
  the company running the offer.
* One row sections use a snapping horizontal rail: 4 to 6 cards on desktop, one
  swipeable card at a time on a phone, no page level horizontal overflow.
* Every section has its own empty state with a useful next step. Nothing is
  hardcoded: all eight sections read from the existing models with per-section
  limits, so the page issues small queries only.
* "Own a workshop?" became "Are you an automotive service provider?" with
  **List your business** and **Become a partner**, covering all four types.


---

# Release 18.0.4.1.0

* **Registration is per company type.** Choosing Spare Parts Supplier hides
  workshop type and the services checklist and shows parts categories and
  delivery instead; choosing Workshop does the reverse. The heading, eyebrow and
  intro text change with the selection, and the server ignores the fields that
  do not belong to the chosen type, so a supplier can never end up with workshop
  services attached.
* The page is now **Register your company**, as is the website menu entry.
* **Trade licence upload is required for both types** and called out as such.
  Logo, main photo and gallery labels dropped the word "workshop".
* Home page sections 3 and 4 use cards in a grid rather than full width rows, so
  several companies fit across one row.


* 18.0.4.1.1 - the hero "Verified companies" panel had its own hardcoded light
  and dark backgrounds, so it ignored the colours set in Website settings. It
  now reads `--orm-card`, `--orm-border`, `--orm-text` and `--orm-text-muted`
  like every other panel. The only colours still fixed on purpose are the white
  plate behind a company logo and the toggle knob, which need to stay white for
  legibility whatever the palette.
