# -*- coding: utf-8 -*-
# Part of Vertel. See LICENSE file for full copyright and licensing details.
{
    'name': 'Gamification Coin',
    'version': '18.0.1.0.0',
    'category': 'Gamification',
    'summary': 'Spendable coin currency for Odoo',
    'description': """
Gamification Coin
=================
A spendable currency alongside Odoo's karma.

Karma is monotonic: it only ever increases, and ``gamification.karma.rank``
depends on that. Coins are a balance: they can be earned and spent, and the
balance is never allowed to go below zero.

The ledger (``gamification.coin.tracking``) is append-only and mirrors
``gamification.karma.tracking`` in shape, with two deliberate differences:
``gain`` may be negative, and ``_add_coins`` refuses an overdraft.

This module is independent of any consumer. It knows only that someone
credited or debited coins, and where it came from (``origin_ref``). Any module
can credit coins without being a dependency.
""",
    'author': 'Vertel AB',
    'website': 'https://vertel.se',
    'license': 'LGPL-3',
    'depends': ['gamification'],
    'data': [
        'security/gamification_coin_security.xml',
        'security/ir.model.access.csv',
        'wizard/gamification_coin_adjust_wizard_views.xml',
        'views/gamification_coin_tracking_views.xml',
        'views/res_users_views.xml',
        'views/gamification_coin_menus.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
