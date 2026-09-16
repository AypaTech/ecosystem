from odoo import fields, models
from odoo.exceptions import ValidationError


class SelezionaEtichettaReso(models.TransientModel):
    _name = "seleziona.etichetta.reso"
    _description = "Wizard per selezionare un etichetta di reso, in caso ce ne sia più di una"

    def _get_picking_id_domain(self):
        picking_ids_list = self.env.context.get('picking_ids')
        return [('id', 'in', picking_ids_list)]

    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Trasferimento',
        domain=_get_picking_id_domain,
        required=True
    )

    def button_send_mail(self):
        etichetta = self.picking_id.label_url
        if not etichetta:
            # Non dovrebbe mai succedere, dato che tramite context passo al wizard solo i picking che hanno un'etichetta
            raise ValidationError("Non sono riuscito a trovare un etichetta assegnata al trasferimento selezionato.")

        email_template = self.env.ref('aypatech_helpdesk.aypatech_helpdesk_etichetta_cliente')
        email_template.with_context(etichetta=etichetta).send_mail(self.id, force_send=True)
