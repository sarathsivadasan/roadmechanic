# Odex Road Mechanic - Bookings & Quotations

Transactional layer on top of `odex_road_mechanic`. Odoo 18 Community only.

Discovery stays in the directory module; booking, quotation and chat live here.
The directory does not depend on this addon, so it can be installed, upgraded or
removed on its own — and this module is the join point for ODEX WMS later.

## Install

1. Copy `odex_road_mechanic_booking` next to `odex_road_mechanic` in the addons path.
2. Restart Odoo, update the apps list, install "Odex Road Mechanic - Bookings & Quotations".

Depends only on `odex_road_mechanic` (which brings `base`, `mail`, `portal`, `website`).
No `account` dependency: tax is a plain percentage per line, totals use the company currency.

## The three logins

| Role | Group | Portal entry |
|---|---|---|
| Admin | Road Mechanic Admin | Backend: Road Mechanic → Bookings / Quotations / Conversations / Vehicles |
| Garage Partner | Garage Partner | `/my/garage` |
| Customer / Vehicle Owner | Customer / Vehicle Owner | `/my/bookings`, `/my/quotations`, `/my/vehicles` |

Record rules restrict a Garage Partner to bookings, quotations, chats and schedules
of workshops whose `partner_id` is their contact, and a Customer to their own
bookings, quotations, vehicles and chats. Draft quotations are never visible to
the customer.

## Booking flow

    Customer → workshop → service → vehicle → date → free slot → pickup/drop → request
    → Garage Partner accepts → start work → complete
                            ↘ decline / no show / cancel

Slot engine, per workshop:

* working days with a morning and an afternoon block (the gap is the lunch break)
* slot duration, bookings per slot, per-day capacity override
* minimum notice in hours and a booking window in days
* closed dates (whole day) and blocked time ranges inside a day
* availability is computed in the workshop timezone, excludes past and too-soon
  slots, and counts pending/confirmed/in-progress bookings

The slot posted by the browser is re-validated server side, and a Python
constraint blocks overbooking even for concurrent requests.

Garage Partners configure all of this from `/my/garage/schedule/<workshop id>`
or in the backend on the workshop form, tab "Booking Slots".

## Quotation flow

    Booking or inquiry → Garage Partner builds lines → sends
    → Customer confirms or rejects EACH line → status updates automatically

* Line fields: description, type (labour / part / other), qty, unit price,
  discount %, tax %, optional flag.
* The quotation keeps two totals: the quoted total and the total the customer
  actually confirmed.
* States: draft → sent → partially confirmed → confirmed / rejected, plus
  cancelled and expired (a daily cron expires quotations past their validity date).
* Customers respond at `/my/quotation/<id>`; garages edit at
  `/my/garage/quotation/<id>`.

## Chat

Every booking has a thread shared by the customer and the garage
(`/my/booking/<id>#orm-chat` and `/my/garage/booking/<id>#orm-chat`). Sending a
quotation and the customer's line decisions post into the same thread. Admins
read everything under Road Mechanic → Conversations.

## Website routes

| Route | Who |
|---|---|
| `/book/<workshop slug>` | public booking form (shown when the workshop enables bookings) |
| `/road-mechanic/slots` | JSON slot availability |
| `/road-mechanic/booking/submit` | booking POST |
| `/my/bookings`, `/my/booking/<id>` | customer |
| `/my/quotations`, `/my/quotation/<id>` | customer |
| `/my/vehicles` | customer |
| `/my/garage` | garage dashboard |
| `/my/garage/bookings`, `/my/garage/booking/<id>` | garage |
| `/my/garage/quotations`, `/my/garage/quotation/<id>` | garage |
| `/my/garage/schedule/<workshop id>` | garage |

## Known limitations

* The garage calendar in the portal is a list grouped by today / this week /
  upcoming. The full drag-and-drop calendar is the backend view
  (Road Mechanic → Bookings → Calendar).
* Notification emails are not sent; the chat and the portal carry the updates.
  Mail templates can be added without touching the models.
* Pickup and drop-off capture an address as text plus optional coordinates; no
  route planning or driver assignment.
* Service duration is per workshop (slot length), not per service.
* Quotation tax is a percentage per line, not Odoo taxes, and quotations do not
  post to accounting. That belongs in the WMS/invoicing bridge.


## Relationship with the core addon

Vehicles and the chat thread are defined in `odex_road_mechanic`; this addon
extends them with `booking_id`, `quotation_id` and the booking history on a
vehicle. It can be installed and uninstalled without touching the directory or
the marketplace.
