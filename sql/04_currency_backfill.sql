-- Idempotent backfill for databases created before multi-currency support.
-- Runs on every boot; only touches rows that still have default/NULL values.
UPDATE users u SET region_id = r.region_id
FROM regions r
WHERE u.region_id IS NULL AND LOWER(u.country) = LOWER(r.country_name);

UPDATE orders o SET currency_code = c.currency_code,
       exchange_rate_used = c.rate_from_inr,
       display_total_amount = ROUND(o.total_amount * c.rate_from_inr, c.minor_units)
FROM users u, regions r, currencies c
WHERE u.user_id = o.user_id AND r.region_id = u.region_id AND c.currency_code = r.currency_code
  AND o.display_total_amount = 0 AND o.total_amount > 0;

UPDATE order_items oi SET display_price_at_purchase = ROUND(oi.price_at_purchase * o.exchange_rate_used, c.minor_units)
FROM orders o, currencies c
WHERE o.order_id = oi.order_id AND c.currency_code = o.currency_code
  AND oi.display_price_at_purchase = 0 AND oi.price_at_purchase > 0;

UPDATE wallet_transactions wt SET currency_code = c.currency_code,
       exchange_rate_used = c.rate_from_inr,
       display_amount = ROUND(wt.amount * c.rate_from_inr, c.minor_units)
FROM users u, regions r, currencies c
WHERE u.user_id = wt.user_id AND r.region_id = u.region_id AND c.currency_code = r.currency_code
  AND wt.display_amount = 0 AND wt.amount <> 0;

UPDATE user_library SET playtime_seconds = playtime_minutes * 60
WHERE playtime_seconds = 0 AND playtime_minutes > 0;
