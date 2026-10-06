# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils


class CoinTracking(models.Model):
    """Append-only ledger of coin changes.

    Mirrors ``gamification.karma.tracking`` in shape. Two deliberate
    differences:

    * ``gain`` may be negative (coins are spent, karma is not).
    * An overdraft is refused — the balance never goes below zero.
    """

    _name = 'gamification.coin.tracking'
    _description = 'Track Coin Changes'
    _rec_name = 'user_id'
    _order = 'tracking_date desc, id desc'

    user_id = fields.Many2one(
        'res.users', 'User', index=True, required=True, ondelete='cascade')
    old_value = fields.Integer('Old Coin Value', readonly=True)
    new_value = fields.Integer('New Coin Value', required=True)
    gain = fields.Integer(
        'Gain', compute='_compute_gain', readonly=False, store=True)
    consolidated = fields.Boolean('Consolidated')

    tracking_date = fields.Datetime(
        'Tracking Date', default=fields.Datetime.now, readonly=True, index=True)
    reason = fields.Text('Description', default=lambda self: _('Add Manually'))
    origin_ref = fields.Reference(
        string='Source',
        selection=lambda self: self._get_origin_selection_values(),
        default=lambda self: f'res.users,{self.env.user.id}',
    )
    origin_ref_model_name = fields.Char(
        string='Source Type',
        compute='_compute_origin_ref_model_name', store=True)

    def _get_origin_selection_values(self):
        """Models that may appear as the source of a coin change.

        Deliberately open: any installed model may credit coins without this
        module knowing it. This is what makes ``gamification_coin``
        independent of its consumers — the alternative (a curated list) would
        force every source module to depend on this one.

        A consumer can still narrow the list by overriding this method.
        """
        return [
            (model.model, model.name)
            for model in self.env['ir.model'].sudo().search([])
        ]

    @api.depends('old_value', 'new_value')
    def _compute_gain(self):
        for tracking in self:
            tracking.gain = tracking.new_value - tracking.old_value

    @api.depends('origin_ref')
    def _compute_origin_ref_model_name(self):
        for tracking in self:
            if tracking.origin_ref:
                tracking.origin_ref_model_name = tracking.origin_ref._name
            else:
                tracking.origin_ref_model_name = False

    @api.model_create_multi
    def create(self, vals_list):
        """Fill missing ``old_value`` from the user's current balance and
        compute ``new_value`` from ``old_value + gain`` when not supplied.

        Refuses an overdraft: a negative gain that would take the balance
        below zero.
        """
        users = self.env['res.users'].browse([
            vals['user_id']
            for vals in vals_list
            if 'old_value' not in vals and vals.get('user_id')
        ])
        balance_per_user = {user.id: user.coin_balance for user in users}

        for vals in vals_list:
            if 'old_value' not in vals and vals.get('user_id'):
                vals['old_value'] = balance_per_user[vals['user_id']]

            if 'gain' in vals and 'old_value' in vals:
                vals['new_value'] = vals['old_value'] + vals['gain']
                del vals['gain']

            # Overdraft guard: applies to every write path, including manual
            # negative entries created directly.
            new_value = vals.get('new_value')
            old_value = vals.get('old_value', 0)
            if new_value is not None and new_value < 0:
                raise UserError(_(
                    "Coin balance cannot go below zero. "
                    "Attempted: %(old)s %(gain)s = %(new)s.",
                    old=old_value,
                    gain=new_value - old_value,
                    new=new_value,
                ))

        return super().create(vals_list)

    def write(self, vals):
        """The ledger is append-only: amounts and metadata cannot change.

        The only exception is the system flag ``consolidated``, which the
        consolidation cron sets. Every other field is immutable.
        """
        if set(vals) - {'consolidated'}:
            raise UserError(_(
                "Coin ledger entries are immutable. "
                "Create a new entry instead of modifying an existing one."
            ))
        return super().write(vals)

    def unlink(self):
        """The ledger is append-only: existing rows cannot be deleted."""
        raise UserError(_(
            "Coin ledger entries are immutable and cannot be deleted."
        ))

    @api.model
    def _consolidate_cron(self):
        """Mark coin entries older than two months as consolidated.

        Unlike ``gamification.karma.tracking``, this does not delete the
        intermediate rows: the coin ledger is append-only, and the balance is
        derived from the latest row, so marking is enough to let reporting
        exclude settled history. The balance is never touched.
        """
        from_date = date_utils.start_of(
            fields.Datetime.today(), 'month') - relativedelta(months=2)
        return self._process_consolidate(from_date)

    @api.model
    def _process_consolidate(self, from_date, end_date=None):
        """Set ``consolidated=True`` on entries in the given window.

        Idempotent: rows already marked are skipped. The balance is
        unaffected because no ``new_value`` is altered.
        """
        if not end_date:
            end_date = date_utils.end_of(
                date_utils.end_of(from_date, 'month'), 'day')

        old_entries = self.sudo().search([
            ('tracking_date', '>=', from_date),
            ('tracking_date', '<=', end_date),
            ('consolidated', '!=', True),
        ])
        old_entries.write({'consolidated': True})
        return True
