# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Sentinel for "unlimited stock".
UNLIMITED_STOCK = -1


class GamificationReward(models.Model):
    """A finite reward that can be bought for coins.

    The counterpart of ``gamification.badge``: where a badge is unlimited,
    free and granted downwards, a reward has a price, a stock and a
    per-person limit, and is redeemed by the user.
    """

    _name = 'gamification.reward'
    _description = 'Reward'
    _inherit = ['image.mixin']
    _order = 'sequence, cost, name'

    name = fields.Char('Reward', required=True, translate=True)
    description = fields.Html(
        'Description', translate=True, sanitize_attributes=False)
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence', default=10)

    category_id = fields.Many2one(
        'gamification.reward.category', string='Category', ondelete='set null')

    cost = fields.Integer(
        'Cost', required=True, default=100,
        help="Price in coins.")
    stock = fields.Integer(
        'Stock', default=UNLIMITED_STOCK,
        help="Number available. Use -1 for unlimited.")
    limit_per_user = fields.Integer(
        'Limit per User', default=0,
        help="Maximum redemptions per user. Use 0 for no limit.")
    requires_approval = fields.Boolean(
        'Requires Approval', default=True,
        help="If set, a Reward Manager must approve each redemption. "
             "If not, the reward is granted immediately.")

    redemption_ids = fields.One2many(
        'gamification.reward.redemption', 'reward_id', string='Redemptions')
    redemption_count = fields.Integer(
        'Redemption Count', compute='_compute_redemption_count')

    # Optional link to a time-bound competition. The competition itself is a
    # ``gamification.challenge`` — this is only a display link, so the shop
    # can surface it without owning a competition model.
    challenge_ids = fields.Many2many(
        'gamification.challenge', 'gamification_reward_challenge_rel',
        'reward_id', 'challenge_id', string='Competitions')
    challenge_count = fields.Integer(
        'Competition Count', compute='_compute_challenge_count')

    # -- Shop display, computed per current user --
    can_afford = fields.Boolean(
        'Affordable', compute='_compute_shop_availability',
        help="Whether the current user has enough coins.")
    in_stock = fields.Boolean(
        'In Stock', compute='_compute_shop_availability',
        help="Whether the reward is available.")
    available = fields.Boolean(
        'Available', compute='_compute_shop_availability',
        help="Whether the current user may request this reward right now.")

    _sql_constraints = [
        ('cost_positive', 'CHECK(cost >= 0)',
         'The cost cannot be negative.'),
        ('stock_valid', 'CHECK(stock >= -1)',
         'Stock must be -1 (unlimited) or a non-negative number.'),
        ('limit_per_user_valid', 'CHECK(limit_per_user >= 0)',
         'The per-user limit cannot be negative.'),
    ]

    @api.constrains('cost')
    def _check_cost(self):
        for reward in self:
            if reward.cost < 0:
                raise ValidationError(_("The cost cannot be negative."))

    @api.depends('redemption_ids')
    def _compute_redemption_count(self):
        for reward in self:
            reward.redemption_count = len(reward.redemption_ids)

    @api.depends('challenge_ids')
    def _compute_challenge_count(self):
        for reward in self:
            reward.challenge_count = len(reward.challenge_ids)

    @api.depends('cost', 'stock', 'limit_per_user')
    def _compute_shop_availability(self):
        """Whether the current user can request this reward.

        Depends on the current user's balance, so it is contextual: the same
        reward is affordable for one person and not for another.
        """
        user = self.env.user
        balance = user.coin_balance
        for reward in self:
            reward.can_afford = balance >= reward.cost
            reward.in_stock = (
                reward.stock == UNLIMITED_STOCK or reward.stock > 0)
            reward.available = (
                reward.active
                and reward.can_afford
                and reward.in_stock
                and not reward._is_limit_reached(user)
            )

    def _is_limit_reached(self, user):
        """Whether ``user`` has reached this reward's per-person limit."""
        self.ensure_one()
        if not self.limit_per_user:
            return False
        redeemed = self.env['gamification.reward.redemption'].search_count([
            ('reward_id', '=', self.id),
            ('user_id', '=', user.id),
            ('state', 'in', ('approved', 'delivered')),
        ])
        return redeemed >= self.limit_per_user

    def _check_request_allowed(self, user):
        """Raise if ``user`` may not request this reward.

        Checks the three gates in order: the reward must be active and in
        stock, the user must be able to afford it, and the per-person limit
        must not be reached.
        """
        self.ensure_one()
        if not self.active:
            raise UserError(_("%(reward)s is no longer available.",
                              reward=self.name))
        if not self.in_stock:
            raise UserError(_("%(reward)s is out of stock.", reward=self.name))
        if user.coin_balance < self.cost:
            raise UserError(_(
                "%(user)s has %(balance)s coins but %(reward)s costs "
                "%(cost)s.",
                user=user.display_name,
                balance=user.coin_balance,
                reward=self.name,
                cost=self.cost,
            ))
        if self._is_limit_reached(user):
            raise UserError(_(
                "%(user)s has already redeemed %(reward)s the maximum "
                "number of times (%(limit)s).",
                user=user.display_name,
                reward=self.name,
                limit=self.limit_per_user,
            ))

    def _decrease_stock(self):
        """Consume one unit of stock, if the stock is limited.

        Called when a redemption is approved. The stock check happens at
        request time; this only consumes.
        """
        self.ensure_one()
        if self.stock != UNLIMITED_STOCK:
            self.stock -= 1

    def action_redeem(self):
        """Create a redemption of this reward for the current user.

        Opens the newly created redemption so the user sees the result.
        """
        self.ensure_one()
        redemption = self.env['gamification.reward.redemption'].create({
            'user_id': self.env.user.id,
            'reward_id': self.id,
        })
        redemption.action_request()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Redemption'),
            'res_model': 'gamification.reward.redemption',
            'res_id': redemption.id,
            'view_mode': 'form',
            'target': 'current',
        }
