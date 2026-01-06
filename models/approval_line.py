# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApprovalLine(models.Model):
    _name = 'approval.line'
    _description = 'Approval Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    
    # Link ke dokumen mana saja
    res_model = fields.Char('Model Name', required=True, index=True)
    res_id = fields.Integer('Record ID', required=True, index=True)
    res_name = fields.Char('Document Name', compute='_compute_res_name', store=True)
    
    # Urutan approval
    sequence = fields.Integer('Sequence', default=10)
    
    # Siapa yang harus approve
    approver_id = fields.Many2one('res.users', string='Approver', required=True)
    approver_name = fields.Char(related='approver_id.name', string='Approver Name', store=True)
    
    # Status
    state = fields.Selection([
        ('pending', 'Waiting'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True)
    
    # Informasi approval
    approval_date = fields.Datetime('Approval Date', readonly=True)
    notes = fields.Text('Notes')
    
    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                try:
                    record = self.env[rec.res_model].browse(rec.res_id)
                    rec.res_name = record.display_name if record.exists() else 'Unknown'
                except:
                    rec.res_name = 'Unknown'
            else:
                rec.res_name = ''
    
    def action_approve(self):
        """Approve this line"""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('This approval has already been processed.'))
        
        if self.approver_id != self.env.user:
            raise UserError(_('Only the designated approver can approve this.'))
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
        })
        
        # Post message di chatter dokumen
        self._post_approval_message('approved')
        
        # Cek apakah semua approval sudah selesai
        self._check_all_approved()
        
        return True
    
    def action_reject(self):
        """Reject this line"""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('This approval has already been processed.'))
        
        if self.approver_id != self.env.user:
            raise UserError(_('Only the designated approver can reject this.'))
        
        self.write({
            'state': 'rejected',
            'approval_date': fields.Datetime.now(),
        })
        
        # Post message di chatter dokumen
        self._post_approval_message('rejected')
        
        # Notify rejection ke dokumen
        self._notify_rejection()
        
        return True
    
    def _post_approval_message(self, action):
        """Post message di chatter dokumen asli"""
        try:
            record = self.env[self.res_model].browse(self.res_id)
            if record.exists():
                message = _('%s has %s (Step %s)') % (
                    self.approver_name,
                    action,
                    self.sequence
                )
                if self.notes:
                    message += '\n' + _('Notes: %s') % self.notes
                
                record.message_post(body=message)
        except:
            pass
    
    def _check_all_approved(self):
        """Check if all approvals are completed"""
        self.ensure_one()
        
        all_lines = self.search([
            ('res_model', '=', self.res_model),
            ('res_id', '=', self.res_id),
        ])
        
        if all(line.state == 'approved' for line in all_lines):
            # Semua sudah approved, eksekusi action final
            try:
                record = self.env[self.res_model].browse(self.res_id)
                if record.exists() and hasattr(record, '_approval_all_approved'):
                    record._approval_all_approved()
            except:
                pass
    
    def _notify_rejection(self):
        """Notify when rejected"""
        try:
            record = self.env[self.res_model].browse(self.res_id)
            if record.exists() and hasattr(record, '_approval_rejected'):
                record._approval_rejected(self)
        except:
            pass