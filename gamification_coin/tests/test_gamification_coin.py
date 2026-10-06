# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestGamificationCoin(TransactionCase):
    """Coin ledger, balance and overdraft behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Coin Test User',
            'login': 'coin_test_user',
        })
        cls.CoinTracking = cls.env['gamification.coin.tracking']

    def test_balance_zero_without_history(self):
        """A user with no ledger rows has a balance of zero."""
        self.assertEqual(self.user.coin_balance, 0)

    def test_add_coins_credits(self):
        """A positive gain increases the balance."""
        self.user._add_coins(20, reason='Completed a course')
        self.assertEqual(self.user.coin_balance, 20)

    def test_spend_coins_debits(self):
        """A negative gain decreases the balance."""
        self.user._add_coins(30, reason='Earned')
        self.user._add_coins(-15, reason='Redeemed a reward')
        self.assertEqual(self.user.coin_balance, 15)

    def test_balance_follows_latest_row(self):
        """The balance is the new_value of the latest ledger row."""
        self.user._add_coins(10)
        self.user._add_coins(20)
        self.user._add_coins(-25)
        self.assertEqual(self.user.coin_balance, 5)

    def test_reason_and_source_stored(self):
        """Reason and source are recorded on the ledger entry."""
        self.user._add_coins(10, source=self.user, reason='Loyalty bonus')
        entry = self.CoinTracking.search([('user_id', '=', self.user.id)], limit=1)
        self.assertIn('Loyalty bonus', entry.reason)
        self.assertEqual(entry.origin_ref, self.user)

    def test_overdraft_refused(self):
        """Spending more than the balance is refused."""
        self.user._add_coins(30)
        with self.assertRaises(UserError):
            self.user._add_coins(-50)
        self.assertEqual(self.user.coin_balance, 30)

    def test_spend_entire_balance(self):
        """Spending exactly the balance is allowed and leaves zero."""
        self.user._add_coins(30)
        self.user._add_coins(-30)
        self.assertEqual(self.user.coin_balance, 0)

    def test_direct_negative_entry_refused(self):
        """A negative ledger row exceeding the balance is refused on create."""
        with self.assertRaises(UserError):
            self.CoinTracking.create({
                'user_id': self.user.id,
                'old_value': 0,
                'new_value': -10,
            })

    def test_create_fills_old_value_and_new_value(self):
        """create() derives old_value from the balance and new_value from gain."""
        self.user._add_coins(10)
        entry = self.CoinTracking.create({
            'user_id': self.user.id,
            'gain': 5,
        })
        self.assertEqual(entry.old_value, 10)
        self.assertEqual(entry.new_value, 15)
        self.assertEqual(self.user.coin_balance, 15)

    def test_ledger_is_append_only(self):
        """Existing ledger entries cannot be modified."""
        self.user._add_coins(10)
        entry = self.CoinTracking.search([('user_id', '=', self.user.id)], limit=1)
        with self.assertRaises(UserError):
            entry.write({'new_value': 999})
        with self.assertRaises(UserError):
            entry.unlink()

    def test_consolidated_flag_is_writable(self):
        """The consolidation flag may be set; amounts may not."""
        self.user._add_coins(10)
        entry = self.CoinTracking.search([('user_id', '=', self.user.id)], limit=1)
        entry.write({'consolidated': True})
        self.assertTrue(entry.consolidated)

    def test_batch_credits_each_user(self):
        """Batch crediting creates one row per user with the right balance."""
        user_b = self.env['res.users'].create({
            'name': 'Coin Test User B',
            'login': 'coin_test_user_b',
        })
        self.user._add_coins(10)
        self.env['res.users']._add_coins_batch({
            self.user: {'gain': 5, 'reason': 'Batch'},
            user_b: {'gain': 7, 'reason': 'Batch'},
        })
        self.assertEqual(self.user.coin_balance, 15)
        self.assertEqual(user_b.coin_balance, 7)

    def test_coins_independent_of_karma(self):
        """Spending coins does not change karma or rank."""
        self.user.karma = 35
        karma_before = self.user.karma
        rank_before = self.user.rank_id
        self.user._add_coins(30)
        self.user._add_coins(-25)
        self.assertEqual(self.user.karma, karma_before)
        self.assertEqual(self.user.rank_id, rank_before)
        self.assertEqual(self.user.coin_balance, 5)

    def test_consolidation_preserves_balance(self):
        """Consolidation marks old rows without touching the balance."""
        self.user._add_coins(10)
        self.user._add_coins(20)
        balance_before = self.user.coin_balance

        # Consolidate everything up to today.
        self.CoinTracking._process_consolidate(
            from_date='2000-01-01', end_date='2100-01-01')

        self.assertEqual(self.user.coin_balance, balance_before)
        self.assertTrue(all(
            self.CoinTracking.search([('user_id', '=', self.user.id)]).mapped(
                'consolidated')))

    def test_consolidation_is_idempotent(self):
        """Running consolidation twice changes nothing."""
        self.user._add_coins(10)
        self.CoinTracking._process_consolidate(
            from_date='2000-01-01', end_date='2100-01-01')
        balance = self.user.coin_balance
        self.CoinTracking._process_consolidate(
            from_date='2000-01-01', end_date='2100-01-01')
        self.assertEqual(self.user.coin_balance, balance)

    def test_adjust_wizard_requires_reason(self):
        """The manual adjustment wizard requires a reason."""
        with self.assertRaises(Exception):
            self.env['gamification.coin.adjust.wizard'].create({
                'user_id': self.user.id,
                'gain': 100,
            })

    def test_adjust_wizard_grants(self):
        """The wizard grants coins and records the reason."""
        wizard = self.env['gamification.coin.adjust.wizard'].create({
            'user_id': self.user.id,
            'gain': 100,
            'reason': 'Loyalty bonus',
        })
        wizard.action_apply()
        self.assertEqual(self.user.coin_balance, 100)

    def test_adjust_wizard_obeys_overdraft(self):
        """The wizard cannot take the balance below zero."""
        wizard = self.env['gamification.coin.adjust.wizard'].create({
            'user_id': self.user.id,
            'gain': -50,
            'reason': 'Correction',
        })
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertEqual(self.user.coin_balance, 0)
