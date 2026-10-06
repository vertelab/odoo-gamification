# Gamification Coin

A spendable currency alongside Odoo's karma.

## Why a second currency?

Odoo's `gamification.karma` is monotonic. `res.users._add_karma_batch` computes
`new_value = old_value + gain`, and there is no way to spend karma anywhere in
the module. That is deliberate: `gamification.karma.rank` derives a user's rank
from karma, so a balance that could fall would make rank meaningless.

But a reward you cannot spend is not much of a reward. A shop needs a currency
that **goes down**.

`gamification_coin` is that currency. It is a separate ledger, modelled on
`gamification.karma.tracking`, with two deliberate differences:

| | Karma | Coins |
|---|---|---|
| Direction | Only up | Up and down |
| Drives | Rank, badges | A shop |
| Overdraft | N/A | Refused |

Karma is achievement. Coins are currency. Two things that happen to share a
source.

## The ledger

`gamification.coin.tracking` is append-only.

| Field | Meaning |
|---|---|
| `user_id` | Whose coins changed |
| `old_value` | Balance before |
| `gain` | Change (may be negative) |
| `new_value` | Balance after |
| `reason` | Human-readable description |
| `origin_ref` | Source record (a `Reference`) |
| `tracking_date` | When it happened |
| `consolidated` | Set by the consolidation cron |

Entries are immutable. `write()` refuses any change except `consolidated`, and
`unlink()` always refuses. The ledger is the audit trail; it is never rewritten.

## The balance

`res.users.coin_balance` is the `new_value` of the user's latest ledger row.
It is a stored compute with `@api.depends('coin_tracking_ids.new_value')`, so
the ORM invalidates it whenever a row is added — the same pattern Odoo uses for
`res.users.karma`. A user with no history has a balance of 0.

Nothing is stored twice: the ledger is the single source of truth.

## API

### Credit or spend coins

```python
# Grant 20 coins
user._add_coins(20, source=some_record, reason='Completed a course')

# Spend 15 coins
user._add_coins(-15, source=redemption, reason='Redeemed: long lunch')
```

`source` is stored as `origin_ref` and may be any record. `gamification_coin`
does not need to know the model — that is what makes it independent.

### Batch

```python
self.env['res.users']._add_coins_batch({
    user_a: {'gain': 10, 'reason': 'Weekly survey'},
    user_b: {'gain': 5, 'reason': 'Referral'},
})
```

One ledger row per user, each with its own running balance, in one transaction.

### Overdraft

A negative gain that would take the balance below zero is refused, with a
message naming the user and the shortfall. This applies both in `_add_coins`
and in a direct `create` on the ledger, so manual corrections are covered too.

```
balance 30, _add_coins(-50)  →  UserError
balance 30, _add_coins(-30)  →  ok, balance 0
```

## Manual adjustment

A **Coin Manager** can adjust a balance from the user form ("Adjust Coins").
The reason is mandatory. The adjustment goes through `_add_coins`, so it obeys
the overdraft rule and is recorded like any other change.

## Consolidation

The ledger grows without bound. A monthly cron marks entries older than two
months as `consolidated`.

Unlike `gamification.karma.tracking` — which deletes intermediate rows and
keeps a summary — this **only marks**. The ledger is append-only, so rows stay.
The balance is unaffected: it is still the latest `new_value`, and no value is
altered. Marking is enough to let reporting exclude settled history.

## Independence

This module depends only on `gamification`. It does not reference rollout, a
shop, or any reward model.

Any module may credit coins without being a dependency:

```python
self.env.user._add_coins(5, source=self, reason='Did something worth coins')
```

The source module does not need to be installed together with this one, and
this one does not need to know it exists.

## Security

| Group | Can |
|---|---|
| Internal User | Read own ledger entries and own balance |
| Coin Manager | Read the whole ledger, adjust balances manually |

Record rules restrict regular users to their own entries.

## Tests

```bash
checkmodule -d test_db -m gamification_coin -t --drop
```

20 tests covering crediting, spending, overdraft, the balance computation,
immutability, batch crediting, independence from karma, consolidation, and the
adjustment wizard.
