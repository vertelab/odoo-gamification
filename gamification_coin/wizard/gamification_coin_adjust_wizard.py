# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class CoinAdjustWizard(models.TransientModel):
    """Manually grant or deduct coins, with a mandatory reason.

    The adjustment is recorded in the ledger like any other change, so a
    manual correction is as traceable as an automatic one.
    """

    _name = 'gamification.coin.adjust.wizard'
    _description = 'Adjust Coin Balance'

    user_id = fields.Many2one(
        'res.users', string='User', required=True)
    gain = fields.Integer(
        'Coins', required=True,
        help="Positive to grant coins, negative to deduct them.")
    reason = fields.Text(
        'Reason', required=True,
        help="Why the balance is being adjusted. Stored on the ledger entry.")

    def action_apply(self):
        """Apply the adjustment through the standard coin API."""
        self.ensure_one()
        self.user_id._add_coins(
            self.gain,
            source=self.user_id,
            reason=self.reason,
        )
        return {'type': 'ir.actions.act_window_close'}
