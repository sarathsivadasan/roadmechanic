# Odex Road Mechanic

Workshop directory for Odoo 18 **Community** — branded as **ROAD MECHANIC / UAE AUTO SOLUTIONS**.

The addon renders directory content only. The standard Odoo website header and
footer stay in place and keep controlling the logo, menus and footer links. All
custom CSS is scoped under `.odex-road-mechanic`.

## Install

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
  * *Directory Hero Image* — hero background. A branded placeholder is used when
    empty.
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
