# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GamificationRewardRedemption(models.Model):
    """A request to redeem a reward.

    A redemption is a process, not an event: ``requested``, ``approved``,
    ``delivered`` (or ``rejected``). Coins are deducted exactly once, when
    the redemption is approved.
    """

    _name = 'gamification.reward.redemption'
    _description = 'Reward Redemption'
    _inherit = ['mail.thread']
    _order = 'requested_at desc, id desc'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, index=True,
        ondelete='cascade', default=lambda self: self.env.user)
    reward_id = fields.Many2one(
        'gamification.reward', string='Reward', required=True,
        ondelete='restrict')
    cost_paid = fields.Integer(
        'Cost Paid', readonly=True,
        help="Coins deducted when the redemption was approved.")

    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected'),
    ], string='Status', default='requested', required=True, tracking=True,
        index=True)

    requested_at = fields.Datetime(
        'Requested On', default=fields.Datetime.now, readonly=True)
    approved_by = fields.Many2one(
        'res.users', string='Approved By', readonly=True)
    approved_at = fields.Datetime('Approved On', readonly=True)
    delivered_by = fields.Many2one(
        'res.users', string='Delivered By', readonly=True)
    delivered_at = fields.Datetime('Delivered On', readonly=True)
    rejected_by = fields.Many2one(
        'res.users', string='Rejected By', readonly=True)
    rejected_at = fields.Datetime('Rejected On', readonly=True)
    reject_reason = fields.Text('Rejection Reason', readonly=True)

    # -- Traceability --
    coin_tracking_ids = fields.One2many(
        'gamification.coin.tracking', compute='_compute_coin_tracking_ids',
        string='Coin Entries')
    coin_entry_count = fields.Integer(
        'Coin Entry Count', compute='_compute_coin_tracking_ids')

    @api.depends('state')
    def _compute_coin_tracking_ids(self):
        """The ledger entries this redemption caused.

        The ledger stores the source as ``origin_ref``; there is no inverse
        field, so the link is resolved here.
        """
        CoinTracking = self.env['gamification.coin.tracking']
        for redemption in self:
            entries = CoinTracking.search([
                ('origin_ref', '=', f'{redemption._name},{redemption.id}'),
            ])
            redemption.coin_tracking_ids = entries
            redemption.coin_entry_count = len(entries)

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Validate a request before creating it.

        Checks the balance, the stock and the per-person limit. Coins are
        *not* deducted here — that happens on approval.
        """
        for vals in vals_list:
            reward = self.env['gamification.reward'].browse(
                vals.get('reward_id'))
            user = self.env['res.users'].browse(
                vals.get('user_id', self.env.user.id))
            reward._check_request_allowed(user)
        return super().create(vals_list)

    def action_request(self):
        """Request the reward, auto-approving when approval is not required."""
        for redemption in self:
            if redemption.state != 'requested':
                raise UserError(_(
                    "Only a requested redemption can be requested."))
            if not redemption.reward_id.requires_approval:
                redemption._approve()
        return True

    # ------------------------------------------------------------------
    # Approve / reject / deliver
    # ------------------------------------------------------------------
    def action_approve(self):
        """Approve the redemption: deduct coins and consume stock."""
        self._check_manager()
        for redemption in self:
            redemption._approve()
        return True

    def _approve(self):
        """Shared approval path, used by both the button and auto-approval.

        Deducts coins exactly once and decreases stock. Idempotent: an
        already-approved redemption is left alone.
        """
        self.ensure_one()
        if self.state == 'approved':
            return
        if self.state != 'requested':
            raise UserError(_(
                "Only a requested redemption can be approved."))

        reward = self.reward_id
        user = self.user_id

        # Revalidate the balance: it may have fallen while the request waited.
        if user.coin_balance < reward.cost:
            raise UserError(_(
                "%(user)s has %(balance)s coins but the reward costs "
                "%(cost)s. The balance fell while the request was waiting.",
                user=user.display_name,
                balance=user.coin_balance,
                cost=reward.cost,
            ))

        # Deduct coins. The ledger entry's origin_ref points back here, which
        # is what makes the deduction traceable to the request.
        user._add_coins(
            -reward.cost,
            source=self,
            reason=_("Redeemed: %(reward)s", reward=reward.name),
        )
        reward._decrease_stock()

        self.write({
            'state': 'approved',
            'cost_paid': reward.cost,
            'approved_by': self.env.user.id,
            'approved_at': fields.Datetime.now(),
        })

    def action_reject(self):
        """Reject the redemption. No coins are deducted, no stock consumed."""
        self._check_manager()
        for redemption in self:
            if redemption.state not in ('requested', 'approved'):
                raise UserError(_(
                    "Only a requested or approved redemption can be rejected."))
            redemption.write({
                'state': 'rejected',
                'rejected_by': self.env.user.id,
                'rejected_at': fields.Datetime.now(),
            })
        return True

    def action_deliver(self):
        """Mark the reward as handed over. No further coins are deducted."""
        self._check_manager()
        for redemption in self:
            if redemption.state != 'approved':
                raise UserError(_(
                    "Only an approved redemption can be delivered."))
            redemption.write({
                'state': 'delivered',
                'delivered_by': self.env.user.id,
                'delivered_at': fields.Datetime.now(),
            })
        return True

    def _check_manager(self):
        """Approving, rejecting and delivering require the manager group."""
        if not self.env.user.has_group(
                'gamification_coin_reward.group_reward_manager'):
            raise UserError(_(
                "Only a Reward Manager may approve, reject or deliver "
                "a redemption."))
