# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApprovalMixin(models.AbstractModel):
    _name = 'approval.mixin'
    _description = 'Approval Mixin'
    
    approval_line_ids = fields.One2many(
        'approval.line',
        inverse_name='res_id',
        domain=lambda self: [('res_model', '=', self._name)],
        string='Approval Lines',
        auto_join=True
    )
    
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval Status', default='draft', tracking=True, copy=False)
    
    is_approver = fields.Boolean(
        'Is Approver',
        compute='_compute_is_approver',
        help='Current user can approve this document'
    )
    
    approval_count = fields.Integer(
        'Approval Count',
        compute='_compute_approval_count'
    )
    
    @api.depends('approval_line_ids')
    def _compute_is_approver(self):
        """Check if current user is an approver"""
        current_user = self.env.user
        for rec in self:
            rec.is_approver = any(
                line.approver_id == current_user and line.state == 'pending'
                for line in rec.approval_line_ids
            )
    
    @api.depends('approval_line_ids')
    def _compute_approval_count(self):
        """Count approval lines"""
        for rec in self:
            rec.approval_count = len(rec.approval_line_ids)
    
    def action_request_approval(self):
        """Request approval - akan create approval lines"""
        self.ensure_one()
        
        # Hapus approval line lama jika ada
        old_lines = self.env['approval.line'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ])
        if old_lines:
            old_lines.unlink()
        
        # Get approvers - harus di-override di model turunan
        approvers = self._get_approvers()
        
        if not approvers:
            raise UserError(_(
                'No approvers found. Please configure approvers first or check HR structure.'
            ))
        
        # Create approval lines
        for seq, approver in enumerate(approvers, start=1):
            self.env['approval.line'].create({
                'res_model': self._name,
                'res_id': self.id,
                'sequence': seq * 10,
                'approver_id': approver.id,
            })
        
        self.approval_state = 'waiting'
        
        # Post message
        self.message_post(
            body=_('Approval requested. Waiting for %s approver(s).') % len(approvers)
        )
        
        return True
    
    def _get_approvers(self):
        """
        Override method ini untuk menentukan siapa saja approver
        
        Return: recordset res.users
        
        Contoh sederhana:
            # Ambil manager dari user yang buat dokumen
            if self.user_id:
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', self.user_id.id)
                ], limit=1)
                
                if employee and employee.parent_id:
                    return employee.parent_id.user_id
            
            return self.env['res.users']
        """
        # Default: cari manager dari user_id (jika ada field user_id)
        if hasattr(self, 'user_id') and self.user_id:
            employee = self.env['hr.employee'].search([
                ('user_id', '=', self.user_id.id)
            ], limit=1)
            
            if employee and employee.parent_id and employee.parent_id.user_id:
                return employee.parent_id.user_id
        
        return self.env['res.users']
    
    def action_approve_line(self):
        """User approve their line"""
        self.ensure_one()
        
        line = self.env['approval.line'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('approver_id', '=', self.env.user.id),
            ('state', '=', 'pending'),
        ], limit=1)
        
        if not line:
            raise UserError(_('You are not authorized to approve this document.'))
        
        line.action_approve()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approved'),
                'message': _('You have approved this document.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject_line(self):
        """User reject their line"""
        self.ensure_one()
        
        line = self.env['approval.line'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('approver_id', '=', self.env.user.id),
            ('state', '=', 'pending'),
        ], limit=1)
        
        if not line:
            raise UserError(_('You are not authorized to reject this document.'))
        
        line.action_reject()
        self.approval_state = 'rejected'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rejected'),
                'message': _('You have rejected this document.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_view_approval_lines(self):
        """Open approval lines view"""
        self.ensure_one()
        return {
            'name': _('Approval Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.line',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id}
        }
    
    def _approval_all_approved(self):
        """
        Called when all approvals are done
        
        Override method ini untuk action setelah semua approved
        
        Contoh:
            def _approval_all_approved(self):
                super()._approval_all_approved()
                self.action_confirm()  # Confirm dokumen
        """
        self.approval_state = 'approved'
        self.message_post(body=_('All approvals completed. Document approved.'))
    
    def _approval_rejected(self, line):
        """
        Called when approval rejected
        
        Override method ini untuk action setelah rejected
        
        Args:
            line: approval.line record yang reject
        """
        self.approval_state = 'rejected'
        self.message_post(
            body=_('Document rejected by %s') % line.approver_name
        )