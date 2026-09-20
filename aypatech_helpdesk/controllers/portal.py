# Copyright 2026 - Aypa Tech - www.aypatech.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

import base64

from odoo import fields, http
from odoo.http import request


class AypatechHelpdeskPortal(http.Controller):
    """Default customer-facing ticket portal. Products built on top of this module
    (e.g. a marketplace app with its own contracts/categories) are free to build their
    own portal UI against the ``aypatech.helpdesk.ticket`` model instead of using this one."""

    def _get_my_tickets_domain(self):
        return [('partner_id', '=', request.env.user.partner_id.id)]

    @http.route('/my/tickets', type='http', auth='user', website=True)
    def portal_tickets_list(self, status='open', **kwargs):
        Ticket = request.env['aypatech.helpdesk.ticket'].sudo()
        domain = self._get_my_tickets_domain()
        if status == 'closed':
            domain += [('stage_id.closed', '=', True)]
        else:
            domain += [('stage_id.closed', '=', False)]
            status = 'open'

        tickets = Ticket.search(domain, order='create_date desc')
        open_count = Ticket.search_count(self._get_my_tickets_domain() + [('stage_id.closed', '=', False)])
        closed_count = Ticket.search_count(self._get_my_tickets_domain() + [('stage_id.closed', '=', True)])

        return request.render('aypatech_helpdesk.portal_tickets_list', {
            'tickets': tickets,
            'status': status,
            'open_count': open_count,
            'closed_count': closed_count,
        })

    @http.route('/my/tickets/new', type='http', auth='user', website=True, methods=['GET'])
    def portal_ticket_new(self, **kwargs):
        categories = request.env['aypatech.helpdesk.category'].sudo().search([])
        return request.render('aypatech_helpdesk.portal_ticket_new', {
            'categories': categories,
            'error': kwargs.get('error'),
        })

    @http.route('/my/tickets/new', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_new_save(self, **post):
        subject = (post.get('subject') or '').strip()
        description = (post.get('description') or '').strip()
        priority = post.get('priority') or '0'
        category_id = post.get('category_id')

        if not subject:
            return request.redirect('/my/tickets/new?error=Please+fill+in+a+subject')

        vals = {
            'name': subject,
            'description': description,
            'priority': priority if priority in ('0', '1', '2', '3') else '0',
            'category_id': int(category_id) if category_id else False,
            'partner_id': request.env.user.partner_id.id,
            'partner_name': request.env.user.name,
            'partner_email': request.env.user.email,
        }
        ticket = request.env['aypatech.helpdesk.ticket'].sudo().create(vals)
        return request.redirect('/my/tickets/%d?success=created' % ticket.id)

    @http.route('/my/tickets/<int:ticket_id>', type='http', auth='user', website=True)
    def portal_ticket_detail(self, ticket_id, **kwargs):
        ticket = request.env['aypatech.helpdesk.ticket'].sudo().browse(ticket_id)
        current_partner = request.env.user.partner_id
        is_allowed = ticket.exists() and (
            ticket.partner_id.id == current_partner.id or
            current_partner in ticket.message_partner_ids
        )
        if not is_allowed:
            return request.redirect('/my/tickets')

        if ticket.unread_by_customer:
            ticket.unread_by_customer = False

        messages = ticket.message_ids.sudo().filtered(
            lambda m: m.message_type == 'comment' and (not m.subtype_id or not m.subtype_id.internal)
        ).sorted(key=lambda m: m.date or m.create_date)

        closing_stages = request.env['aypatech.helpdesk.stage'].sudo().search([('closed', '=', True)])

        return request.render('aypatech_helpdesk.portal_ticket_detail', {
            'ticket': ticket,
            'messages': messages,
            'closing_stages': closing_stages,
            'success': kwargs.get('success'),
        })

    _REPLY_ATTACHMENT_ALLOWED_MIMETYPES = ('image/png', 'image/jpeg', 'application/pdf')
    _REPLY_ATTACHMENT_MAX_BYTES = 3 * 1024 * 1024  # 3MB

    @http.route('/my/tickets/<int:ticket_id>/reply', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_reply(self, ticket_id, **post):
        ticket = request.env['aypatech.helpdesk.ticket'].sudo().browse(ticket_id)
        current_partner = request.env.user.partner_id
        is_allowed = ticket.exists() and (
            ticket.partner_id.id == current_partner.id or
            current_partner in ticket.message_partner_ids
        )
        if not is_allowed:
            return request.redirect('/my/tickets')

        if ticket.stage_id.closed:
            return request.redirect('/my/tickets/%d' % ticket.id)

        body = (post.get('body') or '').strip()
        if not body:
            return request.redirect('/my/tickets/%d' % ticket.id)

        attachment_ids = []
        upload = request.httprequest.files.get('attachment')
        if upload and upload.filename:
            data = upload.read()
            if data and len(data) <= self._REPLY_ATTACHMENT_MAX_BYTES and \
                    upload.content_type in self._REPLY_ATTACHMENT_ALLOWED_MIMETYPES:
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': upload.filename,
                    'raw': data,
                    'res_model': 'aypatech.helpdesk.ticket',
                    'res_id': ticket.id,
                    'mimetype': upload.content_type,
                })
                attachment_ids.append(attachment.id)

        ticket.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=current_partner.id,
            attachment_ids=attachment_ids,
        )
        return request.redirect('/my/tickets/%d?success=replied' % ticket.id)

    @http.route('/my/tickets/<int:ticket_id>/close', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_close(self, ticket_id, **post):
        ticket = request.env['aypatech.helpdesk.ticket'].sudo().browse(ticket_id)
        current_partner = request.env.user.partner_id
        if not ticket.exists() or ticket.partner_id.id != current_partner.id:
            return request.redirect('/my/tickets')

        stage_id = post.get('stage_id')
        if stage_id:
            ticket.sudo().action_close_from_portal(int(stage_id))
        return request.redirect('/my/tickets/%d' % ticket.id)
