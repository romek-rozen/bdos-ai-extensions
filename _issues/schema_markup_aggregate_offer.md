---
title: schema_check rejects valid AggregateOffer product markup
status: fixed
labels:
  - bug
  - schema-check
---

**Fixed** on branch `fix/schema-aggregate-offer`: `validate_product` now validates
offers by type. An `AggregateOffer` is satisfied by `lowPrice`/`highPrice` (either
bound) + `priceCurrency` and does not require its own `availability`; a plain `Offer`
still requires `price` + `priceCurrency` + `availability`. See `_validate_offer` in
`schema_check/api.py` and `tests/test_schema_check.py`.


Small bug in `schema_check`: `validate_product()` reports `missing_required: ['offers.price']`
for products that use `AggregateOffer` (a price range with `lowPrice`/`highPrice` instead of
`price`). As a result, valid pages are marked as `merchant_ready=False`.

Repro: any `Product` with `"@type": "AggregateOffer"`.

Everything else works well.
