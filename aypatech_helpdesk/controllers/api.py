# Copyright 2022 - Huroos srl - www.huroos.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
_logger = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
DATETIME_FORMAT_JSON = "%Y-%m-%d  %H:%M:%S"
AUTH_TOKEN_LENGHT = 25
AUTH_TOKEN_HOURS_DURATION = 12
SKU_BLACK_LIST = ["shopifyshippingproduct", "shopifydiscountproduct"]


def _manage_exception(ex):
    """
        ValueError = 400
        FileNotFoundError = 404
        AccessError = 401
        Exception = 500
    """

    if type(ex) == ValueError:
        error_code = 400
    elif type(ex) == FileNotFoundError:
        error_code = 404
    elif type(ex) == AccessError:
        error_code = 401
    else:
        error_code = 500

    return {
            "status": error_code,
            "detail": "Exception occurred",
            "data": {
                "exception": ex
            }
        }


def _check_api_rma_auth_token(json_data):
    
    if not json_data or "auth_token" not in json_data:
        raise ValueError(f"Missing auth_token parameter.")
    auth_token = json_data["auth_token"]

    # Checking token is valid
    is_valid = request.env["api_session.utils"].sudo().check_auth_token_is_valid(auth_token)

    if not is_valid:
        raise ValueError(f"Parameter auth_token not correct: {auth_token}.")
    if "data" not in json_data or not json_data["data"]:
        raise ValueError(f"Missing data value.")

    return json_data["data"]


class api(http.Controller):

    @http.route('/api/get_authentication/', type='http', auth="none", methods=['GET'], csrf=False)
    def get_authentication(self):
        """
        {
            "api_rma_password": "API_PWD"
        }
        :return:
        """


        try:
            json_data = request.get_json_data()

            # Checking authentication password
            if "api_rma_password" not in json_data:
                raise ValueError(f"Missing parameter: api_rma_password.")

            api_password = json_data["api_rma_password"]

            # Getting session
            api_session = request.env["api_session.utils"].sudo().get_auth_token(api_password)
            if not api_session:
                raise ValueError(f"Parameter api_rma_password uncorrect: {api_password}.")

            data= {
                "status": 200,
                "detail": "auth_token created",
                "data": {
                    "auth_token": api_session.auth_token,
                    "expiration_date": api_session.auth_token_expiration.strftime(DATETIME_FORMAT_JSON)
                }
            }
            return http.request.make_json_response(data)
        except Exception as ex:
            exception = _manage_exception(ex)
            return exception

    @http.route('/api/get_order/', type='http', auth="none", methods=['GET'], csrf=False)
    def get_order(self):
        """
        {
             "auth_token": "token",
            data: {
                "order_number": "order_number or shopify_id"
            }
        }

        """

        try:
            json_data = request.get_json_data()

            # Checking auth token
            data = _check_api_rma_auth_token(json_data)

            if not data or "order_number" not in data:
                raise ValueError(f"Missing parameter order_number.")

            order_number = data["order_number"].strip()
            order_src = request.env['sale.order'].sudo().search(['|', ("name", "=", order_number), ("shopify_order_id", "=", order_number)])
            order_lines = []
            if not order_src or len(order_src) == 0:
                raise FileNotFoundError(f"Order {order_number} not found.")
            order = request.env['sale.order'].sudo().browse(order_src["id"])

            for ol in order.order_line:
                if not ol.display_type and ol.product_id.default_code not in SKU_BLACK_LIST:
                    order_lines.append(
                        {
                            "sku": ol.product_id.default_code,
                            "product": ol.product_id.display_name,
                            "qty": ol.product_uom_qty
                        }
                    )
            response= {
                "status": 200,
                "detail": f"Order {order.name} {order.date_order.strftime(DATETIME_FORMAT)} - {len(order_lines)} products lines.",
                "data": {
                    "shopify_order_number": order.shopify_order_number or '',
                    "customer": {
                        "id": order.partner_id.id,
                        "name": order.partner_id.display_name,
                        "street": order.partner_id.street,
                        "zip": order.partner_id.zip,
                        "city": order.partner_id.city,
                        "state": order.partner_id.state_id.name if order.partner_id.state_id else '',
                        "country": order.partner_id.country_id.name if order.partner_id.country_id else '',
                        "vat": order.partner_id.vat or '',
                        "email": order.partner_id.email or '',
                        "phone": order.partner_id.phone or ''
                     },
                    "date": order.date_order.strftime(DATETIME_FORMAT),
                    "warehouse": order.warehouse_id.name,
                    "order_lines": order_lines
                }
            }
            return http.request.make_json_response(response)
        except Exception as ex:
            exception = _manage_exception(ex)
            return exception

    @http.route('/api/create_rma_ticket/', type='http', auth="none", methods=['POST'], csrf=False)
    def create_rma_ticket(self):
        """        {
            "auth_token": "token",
            data: {
                "order": "order_number or shopify_id",
                "customer_name": "customer_name",


        }
        """

        try:
            json_data = request.get_json_data()

            data = _check_api_rma_auth_token(json_data)
            ticket_data = {
                "name": f"{data['customer_name']} - Order: {data['order']}",
                "json_return": data
            }
            
            new_ticket = request.env["helpdesk.ticket"].sudo().with_user(request.context.get('uid',2)).create(ticket_data)
            try:
                new_ticket.set_return_values_from_json()
            except Exception as ex:
                pass
            response={
                "status": 200,
                "detail": f"RMA ticket created",
                "data": {
                    "ticket_id": f"#{new_ticket.id}"
                }
            }
            return http.request.make_json_response(response)

        except Exception as ex:
            exception = _manage_exception(ex)
            return exception


