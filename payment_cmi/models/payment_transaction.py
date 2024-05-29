# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import re

from werkzeug import urls

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_repr

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_cmi.controllers.main import CmiController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider, prefix=None, separator='-', **kwargs):
        """ Override of payment to ensure that CMI requirements for references are satisfied.

        CMI requirements for transaction are as follows:
        - References must be unique at provider level for a given merchant account.
          This is satisfied by singularizing the prefix with the current datetime. If two
          transactions are created simultaneously, `_compute_reference` ensures the uniqueness of
          references by suffixing a sequence number.

        :param str provider: The provider of the provider handling the transaction
        :param str prefix: The custom prefix used to compute the full reference
        :param str separator: The custom separator used to separate the prefix from the suffix
        :return: The unique reference for the transaction
        :rtype: str
        """
        if self.provider_code == 'cmi':
            if not prefix:
                # If no prefix is provided, it could mean that a module has passed a kwarg intended
                # for the `_compute_reference_prefix` method, as it is only called if the prefix is
                # empty. We call it manually here because singularizing the prefix would generate a
                # default value if it was empty, hence preventing the method from ever being called
                # and the transaction from received a reference named after the related document.
                prefix = self.sudo()._compute_reference_prefix(
                    provider, separator, **kwargs
                ) or None
            prefix = payment_utils.singularize_reference_prefix(prefix=prefix, separator=separator)
        return super()._compute_reference(provider, prefix=prefix, separator=separator, **kwargs)

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return CMi-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        base_url = self.get_base_url()
        if self.provider_code != 'cmi':
            return res
        partner = self.env['res.partner'].browse(processing_values['partner_id'])
        origLang = partner.lang.strip().lower()
        arLang = "ar"
        enLang = "en"
        frLang = "fr"
        if frLang in origLang:
            glang = frLang
        elif arLang in origLang:
            glang = arLang
        else:
            glang = enLang
        _logger.info("lang generated:\n%s", glang)
        _logger.info("lang original:\n%s", origLang)
        billing_state = processing_values['billing_partner_state'].name if processing_values.get('billing_partner_state') else ''
        if processing_values.get('billing_partner_country') and processing_values.get('billing_partner_country') == self.env.ref('base.us',
                                                                                                           False):
            billing_state = processing_values['billing_partner_state'].code if processing_values.get('billing_partner_state') else ''
        api_url = self.provider_id.cmi_url_gateway
        cmi_values = {
            'clientid': self.provider_id.cmi_merchant_id,
            'oid': self.reference,
            'amount': float_repr(processing_values['amount'], self.currency_id.decimal_places or 2),
            'currency': '504',
            'TranType': 'PreAuth',
            'storetype': '3D_PAY_HOSTING',
            'hashAlgorithm': 'ver3',
            'rnd': '197328465',
            'llang': glang,
            'refreshtime': '5',
            'encoding': 'UTF-8',
            'BillToName': re.sub(r'[^a-zA-Z0-9 ]+', '', self.partner_name).strip(),
            'email': self.partner_email.strip(),
            'tel': re.sub(r'[^0-9 -]+', ' ', self.partner_phone).strip(),
            'BillToStreet1': re.sub(r'[^a-zA-Z0-9 ]+', ' ', self.partner_address).strip(),
            'BillToCity': re.sub(r'[^a-zA-Z0-9 ]+', '', self.partner_city).strip(),
            'BillToPostalCode': re.sub(r'[^a-zA-Z0-9 ]+', '', self.partner_zip).strip(),
            'BillToCountry': re.sub(r'[^a-zA-Z0-9 ]+', '', self.partner_country_id.name).strip(),
            'shopurl': base_url,
            'failUrl': urls.url_join(self.get_base_url(), CmiController._error_url),
            'okUrl': urls.url_join(self.get_base_url(), CmiController._return_url),
            'callbackUrl': urls.url_join(self.get_base_url(), CmiController._webhook_url), 
            'api_url': api_url,
        }
        cmi_values['hash'] = self.provider_id._cmi_generate_sign('in', cmi_values)
        return cmi_values

    @api.model
    def _get_tx_from_feedback_data(self, provider, data):
        """ Override of payment to find the transaction based on CMi data.

        :param str provider: The provider of the provider that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        :raise: ValidationError if the signature can not be verified
        """

        tx = super()._get_tx_from_feedback_data(provider, data)
        if provider_code != 'cmi':
            return tx

        reference = data.get('oid')
        _logger.warning(
            "received reference   %s",
            reference
        )
        sign = data.get('HASH')
        if not reference or not sign:
            raise ValidationError(
                "CMI: " + _(
                    "Received data with missing oid (%(ref)s) or HASH (%(sign)s).",
                    ref=reference, sign=sign
                )
            )

        tx = self.search([('reference', '=', reference), ('provider', '=', 'cmi')])
        if not tx:
            raise ValidationError(
                "CMI: " + _("No transaction found matching reference %s.", reference)
            )

        # Verify signature

        sign_check = tx.provider_id._cmi_generate_sign('out', data)
        if sign_check != sign:
            raise ValidationError(
                "CMI: " + _(
                    "Invalid sign: received %(sign)s, computed %(check)s.",
                    sign=sign, check=sign_check
                )
            )
        _logger.warning(
            "sign_check  %s |  %s",
            sign_check , sign
        )

        return tx

    def _process_feedback_data(self, data):
        """ Override of payment to process the transaction based on CMi data.

        Note: self.ensure_one()

        :param dict data: The feedback data sent by the provider
        :return: None
        """
        super()._process_feedback_data(data)
        if self.provider_code != 'cmi':
            return

        self.provider_reference = data.get('TransId')

        status = data.get('lapTransactionState')
        if status == 'PENDING':
            self._set_pending()
        elif status == 'APPROVED':
            self._set_done()
        elif status in ('EXPIRED', 'DECLINED'):
            self._set_canceled()
        else:
            _logger.warning(
                "received unrecognized payment state %s for transaction with reference %s",
                status, self.reference
            )
            self._set_error("CMI: " + _("Invalid payment status."))
