# Copyright 2022 - Huroos srl - www.huroos.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """ Adds an activity """
        res = super(StockPicking, self).button_validate()
        for record in self:
            try:
                if record.picking_type_id.code == 'incoming':
                    data = []
                    ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', record.ids[0])], limit=1)
                    if ticket_id:
                        if not ticket_id.user_id:
                            logging.error(f"Missing user for ticket {ticket_id.name}.")
                        else:
                            data.append(
                                {
                                    'res_id': ticket_id.id,
                                    'res_model_id': self.env['ir.model'].search([('model', '=', 'helpdesk.ticket')]).id,
                                    'user_id': ticket_id.user_id.id,
                                    'note': f'Goods return received {record.name}.',
                                    'activity_type_id': self.env.ref('helpdesk.mail_act_helpdesk_handle').id,
                                    'date_deadline': date.today()
                                }
                            )
                            self.env['mail.activity'].create(data)

            except Exception as ex:
                logging.error(f"button_validate: {ex}")
        return res

    def write(self, values):
        """ Updating shippy pro label from stock.picking when sent to ShippyPRO """
        res = super(StockPicking, self).write(values)
        try:
            if self.picking_type_id.code == 'incoming' and "label_url" in values:
                ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', self.ids[0])], limit=1)
                if ticket_id:
                    ticket_id.write({'shippypro_label_url': values["label_url"]})
        except Exception as ex:
            logging.error(f"on_change_label_url: {ex}")

        return res