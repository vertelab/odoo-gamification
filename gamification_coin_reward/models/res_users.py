# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResUsers(models.Model):
    """Keep the shop's affordability in step with the balance.

    ``gamification.reward.can_afford`` depends on the *current user's* coin
    balance, which is not a field on the reward — so Odoo cannot know to
    recompute it when coins change. This module depends on
    ``gamification_coin``, so the invalidation belongs here: the coin module
    stays independent, and the consumer that needs the coupling owns it.
    """

    _inherit = 'res.users'

    def _add_coins_batch(self, values_per_user):
        result = super()._add_coins_batch(values_per_user)
        # The balance changed for these users; drop the cached shop display.
        self.env['gamification.reward'].invalidate_model(
            ['can_afford', 'available'])
        return result
