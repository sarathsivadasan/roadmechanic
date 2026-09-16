{
    'name': 'Odex Road Mechanic',
    'version': '18.0.2.0.1',
    'category': 'Website/Website',
    'summary': 'Road Mechanic - UAE workshop directory, roadside assistance, recovery and parts marketplace',
    'description': """
Odex Road Mechanic
==================

A production ready automotive workshop directory built on the standard Odoo 18
Community Website. It keeps the standard Odoo website header and footer and only
renders the directory content.

Main features
-------------
* Workshop directory with search, filters, sorting and pagination
* Workshop detail pages with photo gallery, services, vehicle brands and map
* Verified / featured workshops with backend controlled priority ranking
* Moderated customer reviews with server side rating recalculation
* Customer inquiries stored as Odoo records with a follow up state machine
* Public workshop registration with an administrator verification workflow
* Workshop owner portal (read/update own workshop only)
* Light and dark theme with a persistent toggle (localStorage)
* Mobile first, responsive layouts
    """,
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
        'website',
    ],
    'data': [
        'security/security.xml',
        'security/service_security.xml',
        'security/primitives_security.xml',
        'security/ir.model.access.csv',
        'data/workshop_type_data.xml',
        'data/service_data.xml',
        'data/vehicle_brand_data.xml',
        'data/location_data.xml',
        'data/service_sequence_data.xml',
        'data/offer_cron.xml',
        'views/service_views.xml',
        'views/workshop_type_views.xml',
        'views/vehicle_brand_views.xml',
        'views/location_views.xml',
        'views/review_views.xml',
        'views/inquiry_views.xml',
        'views/verification_views.xml',
        'views/workshop_views.xml',
        'views/offer_views.xml',
        'views/dashboard_views.xml',
        'views/vehicle_views.xml',
        'views/message_views.xml',
        'views/request_views.xml',
        'views/offer_views.xml',
        'views/notification_views.xml',
        'views/workshop_services_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'views/service_menus.xml',
        'views/website_menu.xml',
        'views/service_website_menu.xml',
        'views/workshop_snippets.xml',
        'views/workshop_templates.xml',
        'views/offer_templates.xml',
        'views/portal_templates.xml',
        'views/service_snippets.xml',
        'views/service_templates.xml',
        'views/service_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'odex_road_mechanic/static/src/css/road_mechanic.css',
            'odex_road_mechanic/static/src/css/services.css',
            'odex_road_mechanic/static/src/js/road_mechanic.js',
            'odex_road_mechanic/static/src/js/services.js',
        ],
        'web.assets_backend': [
            'odex_road_mechanic/static/src/css/road_mechanic_backend.css',
            'odex_road_mechanic/static/src/js/dashboard.js',
            'odex_road_mechanic/static/src/xml/dashboard.xml',
        ],
    },
    'images': ['static/src/img/road_mechanic_logo.png'],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
