# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.
{
    'name': 'Gamification Coin Reward',
    'version': '18.0.1.0.0',
    'category': 'Gamification',
    'summary': 'A shop of finite rewards bought with coins',
    'description': """
Gamification Coin Reward
========================
Finite rewards that can be bought for coins.

A ``gamification.badge`` is an award: it is unlimited, it costs nothing, and it
is granted downwards. A reward is different — it has a price, a stock, and a
per-person limit, and it is redeemed *by* the user.

A redemption is a process, not an event: ``requested``, ``approved``,
``delivered`` (or ``rejected``). Coins are deducted exactly once, when the
redemption is approved, and never more than the balance allows.

This module is a consumer of ``gamification_coin`` and is independent of any
other consumer. It knows nothing about rollout.
""",
    'author': 'Vertel Sverige AB',
    'website': 'https://vertel.se',
    'license': 'LGPL-3',
    'depends': ['gamification_coin', 'gamification'],
    'data': [
        'security/gamification_reward_security.xml',
        'security/ir.model.access.csv',
        'views/gamification_reward_views.xml',
        'views/gamification_reward_redemption_views.xml',
        'views/gamification_reward_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
