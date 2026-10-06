# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class GamificationRewardCategory(models.Model):
    """A grouping for rewards, so the shop can be filtered."""

    _name = 'gamification.reward.category'
    _description = 'Reward Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    reward_ids = fields.One2many(
        'gamification.reward', 'category_id', string='Rewards')
    reward_count = fields.Integer(
        'Reward Count', compute='_compute_reward_count')

    def _compute_reward_count(self):
        for category in self:
            category.reward_count = len(category.reward_ids)
