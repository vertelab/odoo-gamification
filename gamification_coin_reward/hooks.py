# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

# The starter catalogue. Deliberately small and editable — what a reward
# costs and what is on offer is a business decision per customer.
STARTER_CATEGORIES = [
    ('Tid', 10),
    ('Förmån', 20),
    ('Presentkort', 30),
]

STARTER_REWARDS = [
    # (name, cost, stock, category, limit_per_user, requires_approval)
    ('Gå hem en timme tidigt', 100, -1, 'Tid', 0, False),
    ('Längre lunch', 150, -1, 'Tid', 0, False),
    ('En ledig dag', 500, 10, 'Tid', 1, True),
    ('Bio för två', 400, 20, 'Förmån', 0, True),
    ('Presentkort 500 kr', 800, 5, 'Presentkort', 1, True),
]


def post_init_hook(env):
    """Create the starter catalogue of categories and rewards.

    Idempotent: existing records are left alone, so re-running is safe.
    """
    Category = env['gamification.reward.category']
    Reward = env['gamification.reward']

    categories = {}
    for name, sequence in STARTER_CATEGORIES:
        category = Category.search([('name', '=', name)], limit=1)
        if not category:
            category = Category.create({'name': name, 'sequence': sequence})
        categories[name] = category

    for name, cost, stock, category_name, limit, approval in STARTER_REWARDS:
        if Reward.search([('name', '=', name)], limit=1):
            continue
        Reward.create({
            'name': name,
            'cost': cost,
            'stock': stock,
            'category_id': categories[category_name].id,
            'limit_per_user': limit,
            'requires_approval': approval,
        })

    _logger.info(
        "gamification_coin_reward: starter catalogue created "
        "(%s categories, %s rewards)",
        len(STARTER_CATEGORIES), len(STARTER_REWARDS))
