# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    coin_balance = fields.Integer(
        'Coin Balance', compute='_compute_coin_balance', store=True,
        readonly=False,
        help="Spendable coins. Derived from the latest coin ledger entry.",
    )
    coin_tracking_ids = fields.One2many(
        'gamification.coin.tracking', 'user_id', string='Coin Changes',
        groups="base.group_system")

    @api.depends('coin_tracking_ids.new_value', 'coin_tracking_ids.tracking_date')
    def _compute_coin_balance(self):
        """The balance is the ``new_value`` of the user's latest ledger row.

        The ledger is the single source of truth; nothing is stored on the
        user, so the two can never drift apart.
        """
        self.env['gamification.coin.tracking'].flush_model()

        select_query = """
            SELECT DISTINCT ON (user_id) user_id, new_value
              FROM gamification_coin_tracking
             WHERE user_id = ANY(%(user_ids)s)
          ORDER BY user_id, tracking_date DESC, id DESC
        """
        self.env.cr.execute(select_query, {'user_ids': self.ids})

        balance_map = {
            values['user_id']: values['new_value']
            for values in self.env.cr.dictfetchall()
        }

        for user in self:
            user.coin_balance = balance_map.get(user.id, 0)

    def _add_coins(self, gain, source=None, reason=None):
        """Add or spend coins for this user.

        Mirrors ``res.users._add_karma``, with one difference: ``gain`` may be
        negative. An overdraft is refused.

        :param int gain: coins to add (positive) or spend (negative).
        :param source: record that caused the change, stored as ``origin_ref``.
        :param str reason: human-readable description.
        """
        self.ensure_one()
        values = {'gain': gain, 'source': source, 'reason': reason}
        return self._add_coins_batch({self: values})

    def _add_coins_batch(self, values_per_user):
        """Add coins for several users in one transaction.

        :param dict values_per_user: ``{user_record: {'gain': int,
            'source': record|None, 'reason': str|None}}``
        """
        if not values_per_user:
            return

        create_values = []
        for user, values in values_per_user.items():
            origin = values.get('source') or self.env.user
            reason = values.get('reason') or _('Add Manually')
            origin_description = f'{origin.display_name} #{origin.id}'
            old_value = values.get('old_value', user.coin_balance)
            gain = values['gain']

            # Overdraft guard, with a message that names the user.
            if old_value + gain < 0:
                raise UserError(_(
                    "%(user)s has %(balance)s coins and cannot spend "
                    "%(cost)s. Short by %(short)s.",
                    user=user.display_name,
                    balance=old_value,
                    cost=abs(gain),
                    short=abs(old_value + gain),
                ))

            create_values.append({
                'user_id': user.id,
                'old_value': old_value,
                'new_value': old_value + gain,
                'origin_ref': f'{origin._name},{origin.id}',
                'reason': f'{reason} ({origin_description})',
            })

        self.env['gamification.coin.tracking'].sudo().create(create_values)
        return True

    def action_coin_report(self):
        """Open this user's coin ledger."""
        self.ensure_one()

        return {
            'name': _('Coin Updates'),
            'res_model': 'gamification.coin.tracking',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'context': {
                'default_user_id': self.id,
                'search_default_user_id': self.id,
            },
        }
