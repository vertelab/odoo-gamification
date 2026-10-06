# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestGamificationReward(TransactionCase):
    """Reward shop: request, approval, rejection, delivery, traceability."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Reward = cls.env['gamification.reward']
        cls.Redemption = cls.env['gamification.reward.redemption']

        cls.manager_group = cls.env.ref(
            'gamification_coin_reward.group_reward_manager')
        cls.user_group = cls.env.ref(
            'gamification_coin_reward.group_reward_user')

        # A regular user, and a manager.
        cls.user = cls.env['res.users'].create({
            'name': 'Reward User',
            'login': 'reward_user',
            'groups_id': [(6, 0, [cls.user_group.id])],
        })
        cls.manager = cls.env['res.users'].create({
            'name': 'Reward Manager',
            'login': 'reward_manager',
            'groups_id': [(6, 0, [cls.manager_group.id])],
        })

        # A self-service reward and one that needs approval.
        cls.self_service = cls.Reward.create({
            'name': 'Longer lunch',
            'cost': 100,
            'stock': -1,
            'requires_approval': False,
        })
        cls.needs_approval = cls.Reward.create({
            'name': 'A day off',
            'cost': 500,
            'stock': 10,
            'requires_approval': True,
        })

    def _give_coins(self, amount, user=None):
        (user or self.user)._add_coins(amount, reason='Test credit')

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------
    def test_request_creates_requested_state(self):
        """A request creates a redemption in state 'requested'."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        self.assertEqual(redemption.state, 'requested')

    def test_request_without_funds_refused(self):
        """A request beyond the balance is refused."""
        self._give_coins(300)
        with self.assertRaises(UserError):
            self.Redemption.create({
                'user_id': self.user.id,
                'reward_id': self.needs_approval.id,
            })

    def test_request_out_of_stock_refused(self):
        """A request for an out-of-stock reward is refused."""
        self._give_coins(600)
        self.needs_approval.stock = 0
        with self.assertRaises(UserError):
            self.Redemption.create({
                'user_id': self.user.id,
                'reward_id': self.needs_approval.id,
            })

    def test_request_beyond_limit_refused(self):
        """A request beyond the per-person limit is refused."""
        self._give_coins(2000)
        limited = self.Reward.create({
            'name': 'One-off',
            'cost': 100,
            'stock': -1,
            'limit_per_user': 1,
            'requires_approval': False,
        })
        first = self.Redemption.create({
            'user_id': self.user.id, 'reward_id': limited.id})
        first.action_request()
        self.assertEqual(first.state, 'approved')

        with self.assertRaises(UserError):
            self.Redemption.create({
                'user_id': self.user.id, 'reward_id': limited.id})

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------
    def test_approval_deducts_coins(self):
        """Approval deducts the cost exactly once."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(redemption.state, 'approved')
        self.assertEqual(redemption.cost_paid, 500)
        self.assertEqual(self.user.coin_balance, 100)

    def test_approval_decreases_stock(self):
        """Approval consumes one unit of stock."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(self.needs_approval.stock, 9)

    def test_no_deduction_on_request(self):
        """Requesting alone does not deduct coins."""
        self._give_coins(600)
        self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        self.assertEqual(self.user.coin_balance, 600)

    def test_deducted_only_once(self):
        """Approving twice does not deduct twice."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(self.user.coin_balance, 100)
        self.assertEqual(self.needs_approval.stock, 9)

    def test_balance_revalidated_at_approval(self):
        """If the balance falls while waiting, approval is refused."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        # Spend the coins elsewhere while the request waits.
        self.user._add_coins(-550, reason='Spent elsewhere')
        with self.assertRaises(UserError):
            redemption.with_user(self.manager).action_approve()
        self.assertEqual(redemption.state, 'requested')

    def test_unauthorised_approval_refused(self):
        """A user without the manager group cannot approve."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        with self.assertRaises(UserError):
            redemption.with_user(self.user).action_approve()

    def test_approver_recorded(self):
        """The approver is recorded on the redemption."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(redemption.approved_by, self.manager)

    # ------------------------------------------------------------------
    # Auto-approval
    # ------------------------------------------------------------------
    def test_self_service_auto_approves(self):
        """A reward without approval is approved on request."""
        self._give_coins(200)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.self_service.id,
        })
        redemption.action_request()
        self.assertEqual(redemption.state, 'approved')
        self.assertEqual(self.user.coin_balance, 100)

    def test_approval_required_stays_requested(self):
        """A reward needing approval stays requested."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.action_request()
        self.assertEqual(redemption.state, 'requested')
        self.assertEqual(self.user.coin_balance, 600)

    # ------------------------------------------------------------------
    # Rejection and delivery
    # ------------------------------------------------------------------
    def test_rejection_deducts_nothing(self):
        """Rejection leaves the balance and stock untouched."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_reject()
        self.assertEqual(redemption.state, 'rejected')
        self.assertEqual(self.user.coin_balance, 600)
        self.assertEqual(self.needs_approval.stock, 10)

    def test_delivery_records_timestamp(self):
        """Delivery sets the timestamp and does not change coins."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        balance = self.user.coin_balance
        redemption.with_user(self.manager).action_deliver()
        self.assertEqual(redemption.state, 'delivered')
        self.assertTrue(redemption.delivered_at)
        self.assertEqual(self.user.coin_balance, balance)

    def test_deliver_requires_approval_first(self):
        """An unapproved redemption cannot be delivered."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        with self.assertRaises(UserError):
            redemption.with_user(self.manager).action_deliver()

    def test_full_state_progression(self):
        """The state passes through requested, approved, delivered."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        self.assertEqual(redemption.state, 'requested')
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(redemption.state, 'approved')
        redemption.with_user(self.manager).action_deliver()
        self.assertEqual(redemption.state, 'delivered')

    # ------------------------------------------------------------------
    # Stock semantics
    # ------------------------------------------------------------------
    def test_unlimited_stock_stays_negative(self):
        """An unlimited reward keeps its unlimited marker."""
        self._give_coins(1000)
        for _ in range(3):
            redemption = self.Redemption.create({
                'user_id': self.user.id,
                'reward_id': self.self_service.id,
            })
            redemption.action_request()
        self.assertEqual(self.self_service.stock, -1)
        self.assertEqual(self.user.coin_balance, 700)

    def test_limited_stock_can_run_out(self):
        """A limited reward runs out and then refuses requests."""
        self._give_coins(2000)
        small = self.Reward.create({
            'name': 'Two only',
            'cost': 100,
            'stock': 2,
            'requires_approval': False,
        })
        for _ in range(2):
            self.Redemption.create({
                'user_id': self.user.id, 'reward_id': small.id
            }).action_request()
        self.assertEqual(small.stock, 0)
        with self.assertRaises(UserError):
            self.Redemption.create({
                'user_id': self.user.id, 'reward_id': small.id})

    # ------------------------------------------------------------------
    # Shop availability
    # ------------------------------------------------------------------
    def test_can_afford(self):
        """Affordability reflects the current user's balance."""
        self._give_coins(300)
        reward = self.needs_approval.with_user(self.user)
        self.assertFalse(reward.can_afford)
        self._give_coins(300)
        self.assertTrue(reward.can_afford)

    def test_in_stock_reflects_stock(self):
        """In-stock reflects the reward's stock."""
        self.assertTrue(self.needs_approval.in_stock)
        self.needs_approval.stock = 0
        self.assertFalse(self.needs_approval.in_stock)
        self.needs_approval.stock = -1
        self.assertTrue(self.needs_approval.in_stock)

    # ------------------------------------------------------------------
    # Traceability
    # ------------------------------------------------------------------
    def test_ledger_entry_traces_to_redemption(self):
        """The coin deduction resolves back to its redemption."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()

        entry = self.env['gamification.coin.tracking'].search([
            ('user_id', '=', self.user.id),
            ('gain', '<', 0),
        ], limit=1)
        self.assertEqual(entry.origin_ref, redemption)
        self.assertEqual(entry.gain, -500)

    def test_redemption_traces_to_ledger_entry(self):
        """The redemption exposes the coin entry it caused."""
        self._give_coins(600)
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        self.assertEqual(redemption.coin_entry_count, 1)
        self.assertEqual(redemption.coin_tracking_ids.gain, -500)

    # ------------------------------------------------------------------
    # Independence from badges
    # ------------------------------------------------------------------
    def test_no_badge_created(self):
        """Redeeming a reward does not create a badge."""
        self._give_coins(600)
        BadgeUser = self.env['gamification.badge.user']
        before = BadgeUser.search_count([])
        redemption = self.Redemption.create({
            'user_id': self.user.id,
            'reward_id': self.needs_approval.id,
        })
        redemption.with_user(self.manager).action_approve()
        redemption.with_user(self.manager).action_deliver()
        self.assertEqual(BadgeUser.search_count([]), before)

    def test_rewards_separate_from_badges(self):
        """Rewards are a distinct model from badges."""
        self.assertNotEqual(
            self.Reward._name, self.env['gamification.badge']._name)

    # ------------------------------------------------------------------
    # Starter catalogue
    # ------------------------------------------------------------------
    def test_starter_catalogue_exists(self):
        """The post-init hook created a starter catalogue."""
        self.assertTrue(self.Reward.search_count([]) >= 5)
        self.assertTrue(
            self.env['gamification.reward.category'].search_count([]) >= 3)

    # ------------------------------------------------------------------
    # Reuse of gamification.challenge
    # ------------------------------------------------------------------
    def test_challenge_models_a_competition(self):
        """A monthly competition is modelled with gamification.challenge.

        No new competition model is introduced: the core challenge already
        carries period, dates, goal lines and a report.
        """
        definition = self.env['gamification.goal.definition'].create({
            'name': 'Coins earned',
            'computation_mode': 'manually',
            'condition': 'higher',
            'suffix': 'coins',
        })
        challenge = self.env['gamification.challenge'].create({
            'name': 'Month of coins',
            'period': 'monthly',
            'start_date': '2026-10-01',
            'end_date': '2026-10-31',
            'user_ids': [(6, 0, [self.user.id])],
            'line_ids': [(0, 0, {
                'definition_id': definition.id,
                'target_goal': 500,
            })],
        })
        self.assertEqual(challenge.period, 'monthly')
        self.assertTrue(challenge.line_ids)
        self.assertTrue(challenge.report_template_id)

    def test_challenge_uses_core_model(self):
        """The shop does not define its own competition model."""
        self.assertEqual(
            self.env['gamification.challenge']._name,
            'gamification.challenge')
        self.assertNotIn(
            'gamification.reward.challenge',
            self.env.registry.models)
