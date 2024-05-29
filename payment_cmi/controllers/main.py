# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class CmiController(http.Controller):
    _error_url = '/payment/cmi/error'
    _return_url = '/payment/cmi/return'
    _webhook_url = '/payment/cmi/webhook'

    @http.route(_error_url, type='http', auth='public', methods=['POST'], csrf=False,
        save_session=False)
    def cmi_return_error(self, **data):
        """ CMI."""
        _logger.info("entering _handle_feedback_data with data:\n%s", pprint.pformat(data))
        request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'cmi', data
        )
        return request.redirect('/payment/status')

        # return werkzeug.utils.redirect('/payment/process')
    @http.route(_return_url, type='http', auth='public', methods=['POST'], csrf=False,
        save_session=False)
    def cmi_return(self, **data):
        _logger.info("entering _handle_feedback_data with data:\n%s", pprint.pformat(data))
        request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'cmi', data
        )
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
    def cmi_webhook(self, **data):
        _logger.info("handling confirmation from CMI with data:\n%s", pprint.pformat(data))
        state_pol = data.get('ProcReturnCode')
        if state_pol == '00':
            lapTransactionState = 'APPROVED'
            response = 'ACTION=POSTAUTH'
        else:
            lapTransactionState = 'DECLINED'
            response = 'APPROVED'

        data['lapTransactionState']= lapTransactionState

        try:
            request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'cmi', data
        )
        except ValidationError:
            _logger.warning(
               'An error occurred while handling the confirmation from CMI with data:\n%s',
                pprint.pformat(data))
            response = 'FAILURE'
        return response
