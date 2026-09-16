# Copyright 2022 - Huroos srl - www.huroos.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from odoo import fields, models, api, _
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    carrier_return_id = fields.Many2one(
        comodel_name='delivery.carrier',
        string='Corriere/servizio resi'
    )

    carrier_service_id = fields.Many2one('carrier.shippypro.service')

    return_without_carrier = fields.Boolean()

    picking_return_id = fields.Many2one('stock.picking')
    picking_return_type_id = fields.Many2one('stock.picking.type')

    @api.onchange("label_url")
    def move_to_stage_attesa_ricezione(self):
        for record in self:
            stage = self.env['helpdesk.stage'].search([('name', '=', 'Ricezione merce')], limit=1)
            if stage:
                if record.ticket_id:
                    record.ticket_id.stage_id = stage.id if stage and record.ticket_id.stage_id.sequence < stage.sequence else record.ticket_id.stage_id.id
                else:
                    ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', record.picking_id.id)], limit=1)
                    if ticket_id:
                        ticket_id.stage_id = stage.id if stage and ticket_id.stage_id.sequence < stage.sequence else ticket_id.stage_id.id


    def get_carrier_services(self):
        new_picking_id = super()._create_return()
        self.picking_return_id = new_picking_id
        self.picking_return_type_id = new_picking_id.picking_type_id
        self.picking_return_id.is_shippypro_return = True
        self.picking_return_id.carrier_id = self.carrier_return_id
        self.picking_return_id.get_selection_shippypro_service()
        self.carrier_service_id = self.picking_return_id.carrier

        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "stock.return.picking",
            "target": "new",
            "res_id": self.id
        }


    def _create_return(self):

        if not self.picking_return_id:
            new_picking_id = super()._create_return()
        else:
            new_picking_id = self.picking_return_id

        # Updating new picking carrier (if possible)
        # new_picking_id.carrier_id = self.carrier_return_id
        # new_picking_id.get_selection_shippypro_service()
        # all = self.env['carrier.shippypro.service'].search_read([])
        # carriers =list(filter(lambda s: s['carrier_id'] == int(new_picking_id.carrier_id.shippy_pro_carrier_id.carrier_id) and s['service'] == new_picking_id.carrier_id.shippy_pro_carrier_id.carrier_service, all))

        new_picking_id.is_shippypro_return = True
        new_picking_id.carrier_id = self.carrier_return_id
        new_picking_id.carrier = self.carrier_service_id

        if not self.carrier_service_id and not self.return_without_carrier:
            raise UserError("Devi selezionar un servizio di spedizione")

        if self.return_without_carrier:
            new_picking_id.carrier_id = False
            new_picking_id.carrier = False

        logging.info(new_picking_id.carrier_id)

        # If carrier send info to ShippyPRO creating the shipping
        if new_picking_id.carrier:
            for line in new_picking_id.move_ids:
                line.quantity = line.product_uom_qty
            try:
                new_picking_id.start_shippypro_routine()
                if new_picking_id.shippy_pro_order_number:
                    logging.info(new_picking_id.carrier_id)
                    self.ticket_id.shippypro_label_url = new_picking_id.label_url
                    self.ticket_id.action_send_mail()
            except Exception as ex:
                logging.error(f"_create_return: {new_picking_id or 'new_picking_id'} {ex}")
        return new_picking_id

    def action_create_returns(self):
        res = super().action_create_returns()

        stage = self.env.ref('aypatech_helpdesk.stage_attesa_ricezione', raise_if_not_found=False)
        if not stage:
            stage = self.env['helpdesk.stage'].search([('name', '=', 'Attesa Ricezione Merce')], limit=1)
        if stage:
            if self.ticket_id:
                self.ticket_id.stage_id = stage.id if stage and self.ticket_id.stage_id.sequence < stage.sequence else self.ticket_id.stage_id.id
            else:
                ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', self.picking_id.id)], limit=1)
                if ticket_id:
                    ticket_id.stage_id = stage.id if stage and ticket_id.stage_id.sequence < stage.sequence else ticket_id.stage_id.id
        # res['context'] is a frozendict in v19, so rebuild it instead of mutating in place
        res['context'] = dict(res.get('context') or {}, search_default_picking_type_id=self.picking_return_type_id.id)
        return res

    @api.depends('ticket_id.sale_order_id.picking_ids', 'ticket_id.partner_id.commercial_partner_id')
    def _compute_suitable_picking_ids(self):
        for r in self:
            picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'outgoing')])
            domain = [('state', '=', 'done'), ('picking_type_id', 'in', picking_type_id.ids)]
            if r.sale_order_id:
                domain += [('id', 'in', r.sale_order_id.picking_ids._origin.ids)]
            elif r.partner_id:
                domain += [('partner_id', 'child_of', r.partner_id.commercial_partner_id._origin.id)]
            r.suitable_picking_ids = self.env['stock.picking'].search(domain)

            # Imposta di default Corriere/servizio per i resi in base al country del cliente impostato nel team Helpdesk
            if not r.carrier_return_id:
                if r.ticket_id.partner_id.country_id.code == 'IT':
                    r.carrier_return_id = r.ticket_id.team_id.carrier_return_ita_id
                else:
                    r.carrier_return_id = r.ticket_id.team_id.carrier_return_eu_id

class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.onchange("label_url")
    def set_shippy_pro_label_url_ticket(self):
        if not len(self.ids) > 0:
            return
        ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', self.ids[0])], limit=1)
        if ticket_id:
            ticket_id.label_url = self.label_url
