# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'CMI PaymentProvider',
    'version': '2.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 370,
    'summary': 'Payment Provider: CMI Implementation',
    'description': """CMI payment provider""",
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_cmi_templates.xml',
        'data/payment_icon_data.xml',
        'data/payment_provider_data.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
