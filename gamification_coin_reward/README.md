# Gamification Coin Reward

A shop of finite rewards, bought with coins.

## Why not just use badges?

Odoo already has `gamification.badge`. It is the wrong shape for a shop:

| | Badge | Reward |
|---|---|---|
| Granted | Downwards, by someone | Redeemed by the user |
| Cost | None | A price in coins |
| Supply | Unlimited | Finite stock |
| Limit | Per month per sender | Per user, per reward |
| Approval | None | Optional, by a manager |

A badge is an award. A reward is a purchase. This module builds the purchase.

## The models

### `gamification.reward` — the item

| Field | Meaning |
|---|---|
| `name`, `description`, `image_1920` | Presentation in the shop |
| `category_id` | Grouping (Tid, Förmån, Presentkort) |
| `cost` | Price in coins |
| `stock` | Units available. **-1 means unlimited.** |
| `limit_per_user` | Max redemptions per user. **0 means no limit.** |
| `requires_approval` | Whether a manager must approve each redemption |
| `active` | Whether it appears in the shop |
| `can_afford`, `in_stock`, `available` | Computed per current user |
| `challenge_ids` | Optional link to a `gamification.challenge` |

### `gamification.reward.redemption` — the process

| Field | Meaning |
|---|---|
| `user_id`, `reward_id` | Who and what |
| `cost_paid` | Coins deducted (set on approval) |
| `state` | `requested` → `approved` → `delivered`, or `rejected` |
| `requested_at`, `approved_by`/`approved_at` | Request and approval trail |
| `delivered_by`/`delivered_at` | Delivery trail |
| `rejected_by`/`rejected_at`/`reject_reason` | Rejection trail |
| `coin_tracking_ids` | The ledger entries this redemption caused |

## The flow

```
  request ─────────► requested
                       │
        requires_approval = False ──► approved (automatically)
                       │
        requires_approval = True  ──► waits for a Reward Manager
                       │                    │
                       │                    ├── approve ──► approved
                       │                    └── reject  ──► rejected
                       ▼
                    approved ──► delivered
```

**Coins are deducted exactly once — on approval.** Not on request, not on
delivery, not on rejection. The deduction is a negative entry in
`gamification.coin.tracking` whose `origin_ref` points back at the redemption,
so any coin movement can be traced to the request that caused it.

**Stock decreases on approval**, in step with the deduction. A pending request
does not hold stock: the check happens at request time, and the consumption at
approval time.

**The balance is checked twice** — on request (a clear early "no") and again on
approval (in case it fell while waiting). `gamification_coin` refuses an
overdraft regardless, but the shop gives a message that names the reward.

## Groups

| Group | Can |
|---|---|
| **Reward User** | Browse the shop, request rewards, see own redemptions |
| **Reward Manager** | Everything above, plus configure rewards and approve/reject/deliver |

Reward Manager implies Reward User. Record rules keep regular users to their
own redemptions.

## Menus

- **Rewards → Shop** — the catalogue, as a kanban with price and availability
- **Rewards → My Redemptions** — your requests and their status
- **Rewards → Pending Approvals** — for managers
- **Rewards → Configuration** — rewards, categories, all redemptions

## Reuse of `gamification`

Two things are deliberately **not** rebuilt:

**Competitions** use `gamification.challenge`. It already has `period`
(daily/weekly/monthly/…), `start_date`, `end_date`, goal lines and a report
template. A reward can link to one via `challenge_ids`; the shop shows that a
competition is attached. No new competition model exists.

**Measurement** of actions in other systems uses
`gamification.goal.definition` (`model_id`, `field_id`, `domain`,
`batch_mode`). It is a generic measurement definition against any model, with
a batch mode per user. No new measurement engine exists.

## Starter catalogue

On install, `post_init_hook` creates three categories (Tid, Förmån,
Presentkort) and five example rewards. They are ordinary records — edit or
delete them. What a reward costs and what is on offer is a business decision
per customer.

## Independence

This module depends on `gamification_coin` and `gamification` only. It does
not reference rollout.

The dependency runs one way:

```
  gamification_coin              independent — knows nothing of the shop
       ▲
       │ depends
  gamification_coin_reward       this module
```

One piece of coupling is deliberately owned here rather than in the currency:
`can_afford` depends on the current user's balance, which is not a field on the
reward, so Odoo cannot know to recompute it when coins change. This module
overrides `res.users._add_coins_batch` to invalidate the shop cache. The
currency stays independent; the consumer that needs the coupling owns it.

## Tests

```bash
checkmodule -d test_db -m gamification_coin_reward -t --drop
```

28 tests covering request validation (balance, stock, per-person limit),
approval (coins deducted once, stock consumed, balance revalidated,
authorisation), auto-approval, rejection, delivery, unlimited vs finite stock,
shop availability, traceability in both directions, that no badge is created,
and that a competition is modelled with `gamification.challenge`.
