# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import logging
from hashlib import md5


from odoo import api, fields, models
from odoo.tools.float_utils import float_repr
_logger = logging.getLogger(__name__)
SUPPORTED_CURRENCIES = ('MAD')


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('cmi', 'CMI')], ondelete={'cmi': 'set default'})
    cmi_merchant_id = fields.Char(
        string="CMI Merchant ID",
        help="The ID solely used to identify the account with CMi",
        required_if_provider='cmi')
    cmi_merchant_key = fields.Char(
        string="CMI Merchant Store Key", required_if_provider='cmi',
        groups='base.group_system')
    cmi_url_gateway = fields.Char(
        string="CMI Gateway url", required_if_provider='cmi',
        groups='base.group_system')
    cmi_url_gateway = fields.Char(
        string="CMI Gateway url", required_if_provider='cmi',
        groups='base.group_system')
    cmi_tx_confirmation = fields.Boolean(
        string='Automatic confirmation mode',
        default=True,
        help="Check this box to confirm CMI transactions automatically.")

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist CMI providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        return providers

    def _cmi_generate_sign(self, inout, values):
        # def _cmi_generate_sign(self, values):
        """ Generate the shasign for incoming or outgoing communications.
        :param self: the self browse record. It should have a shakey in shakey out
        :param string inout: 'in' (odoo contacting cmi) or 'out' (cmi
                             contacting odoo).
        :param dict values: transaction values

        :return string: shasign
        """
        if inout not in ('in', 'out'):
            raise Exception("Type must be 'in' or 'out'")
        if inout == 'in':
            keys = sorted(values, key=str.casefold)
            keys = [e for e in keys if e not in ('encoding', 'HASH', 'api_url')]
            sign = ''.join(
                '%s|' % (str(values.get(k)).replace("|", "\\|").replace("\\", "\\\\").replace("\n", "")) for k in keys)
            sign += self.cmi_merchant_key.replace("|", "\\|").replace("\\", "\\\\").strip() or ''
            _logger.info("hash in:\n%s", sign)
            shasign = base64.b64encode(hashlib.sha512(sign.encode('utf-8')).digest()).decode()
        else:
            keys = sorted(values, key=str.casefold)
            keys = [e for e in keys if e not in ('encoding', 'HASH', 'lapTransactionState')]

            sign = ''.join(
                '%s|' % (str(values.get(k)).replace("|", "\\|").replace("\\", "\\\\").replace("\n", "")) for k in keys)
            sign += self.cmi_merchant_key.replace("|", "\\|").replace("\\", "\\\\").strip() or ''
            _logger.info("hash out:\n%s", sign)
            shasign = base64.b64encode(hashlib.sha512(sign.encode('utf-8')).digest()).decode()


        return shasign

