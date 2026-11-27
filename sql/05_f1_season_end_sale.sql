-- F1 25 added to the catalog, with an 85% Season End Sale that covers only this game.
-- Applied once by scripts/init_db.py (it checks for the sale title). Adds only.
-- The sale title must not contain "Christmas": that word switches on the Christmas theme.
-- Price is in rupees and does not update by itself. Dates are UTC: 27 Nov 00:00 to 31 Dec 23:59 IST.

INSERT INTO publishers (name, country, founded_year, website) SELECT 'Electronic Arts', 'USA', 1982, 'https://www.ea.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Electronic Arts');
INSERT INTO developers (name, country, website) SELECT 'Codemasters', 'UK', 'https://www.ea.com/games/f1' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Codemasters');
INSERT INTO tags (name, description) VALUES ('Racing', 'High-speed motorsport and open-road driving') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Simulation', 'Life, farming and management systems') ON CONFLICT (name) DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'F1 25', 'The official game of the 2025 Formula 1 season: build your own team in My Team, race through Braking Point 3 and take on the grid in a driving-focused racing simulation.', '2025-05-30', 4999,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Electronic Arts'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Codemasters'), 'Everyone'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'F1 25');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'F1 25' AND t.name IN ('Racing', 'Simulation')
ON CONFLICT DO NOTHING;

INSERT INTO sales (title, start_date, end_date)
VALUES ('SAUNA Season End Sale 2026', '2026-11-26 18:30:00', '2026-12-31 18:29:59');
INSERT INTO sale_items (sale_id, game_id, discount_pct)
SELECT s.sale_id, g.game_id, 85
FROM sales s JOIN games g ON g.title = 'F1 25'
WHERE s.title = 'SAUNA Season End Sale 2026'
ON CONFLICT (sale_id, game_id) DO NOTHING;
