{
    'name': 'Odex Road Mechanic - Bookings & Quotations',
    'version': '18.0.2.0.0',
    'category': 'Website/Website',
    'summary': 'Booking slots, quotations with line level confirmation, and customer/garage chat for Road Mechanic',
    'description': """
Odex Road Mechanic - Bookings & Quotations
==========================================

Adds the transactional layer on top of the Road Mechanic directory:

* Customer vehicles
* Booking engine with per workshop working days, slot duration, slot capacity,
  lunch breaks, closed dates and temporary blocked slots
* Customer booking flow: workshop, vehicle, service, date, available slot,
  pickup / drop-off, problem photos
* Garage Partner booking queue and calendar (accept, start, complete, cancel)
* Quotations with lines the customer confirms or rejects individually
* Chat between the customer and the garage on every booking
* Portal dashboards for the Garage Partner and for the Customer

The directory module stays independent: this addon depends on it, not the
other way around, and it is the natural bridge to ODEX WMS.
    """,
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': [
        'odex_road_mechanic',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/cron_data.xml',
        'views/booking_views.xml',
        'views/quotation_views.xml',
        'views/workshop_booking_views.xml',
        'views/vehicle_booking_views.xml',
        'views/menus.xml',
        'views/booking_templates.xml',
        'views/portal_customer_templates.xml',
        'views/portal_garage_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'odex_road_mechanic_booking/static/src/css/booking.css',
            'odex_road_mechanic_booking/static/src/js/booking.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
