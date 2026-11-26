-- Holiday 2026 content: current prices, 12 more games and an Early Christmas Sale.
-- Applied once by scripts/init_db.py (it checks for the sale title). Adds and updates only.

-- Regular prices in rupees. Past orders keep the price that was paid.
UPDATE games SET base_price = 0 WHERE title = 'Counter-Strike 2';
UPDATE games SET base_price = 2999 WHERE title = 'Half-Life: Alyx';
UPDATE games SET base_price = 509 WHERE title = 'Portal 2';
UPDATE games SET base_price = 2999 WHERE title = 'Cyberpunk 2077';
UPDATE games SET base_price = 1799 WHERE title = 'The Witcher 3: Wild Hunt';
UPDATE games SET base_price = 3599 WHERE title = 'ELDEN RING';
UPDATE games SET base_price = 1100 WHERE title = 'Hades';
UPDATE games SET base_price = 1300 WHERE title = 'Hades II';
UPDATE games SET base_price = 690 WHERE title = 'Hollow Knight';
UPDATE games SET base_price = 2999 WHERE title = 'Baldur''s Gate 3';
UPDATE games SET base_price = 3499 WHERE title = 'Forza Horizon 5';
UPDATE games SET base_price = 1299 WHERE title = 'Pentiment';

INSERT INTO publishers (name, country, founded_year, website) SELECT 'Rockstar Games', 'USA', 1998, 'https://www.rockstargames.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Rockstar Games');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Game Science', 'China', 2014, 'https://www.heishenhua.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Game Science');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Team Cherry', 'Australia', 2014, 'https://www.teamcherry.com.au' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Team Cherry');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Kepler Interactive', 'UK', 2021, 'https://www.kepler-interactive.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Kepler Interactive');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Electronic Arts', 'USA', 1982, 'https://www.ea.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Electronic Arts');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Deep Silver', 'Austria', 2002, 'https://www.deepsilver.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Deep Silver');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Capcom', 'Japan', 1979, 'https://www.capcom.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Capcom');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Xbox Game Studios', 'USA', 2000, 'https://www.xbox.com/xbox-game-studios' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Xbox Game Studios');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'ConcernedApe', 'USA', 2012, 'https://www.stardewvalley.net' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'ConcernedApe');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Re-Logic', 'USA', 2011, 'https://terraria.org' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Re-Logic');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'Pocketpair', 'Japan', 2015, 'https://www.pocketpair.jp' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'Pocketpair');
INSERT INTO publishers (name, country, founded_year, website) SELECT 'TaleWorlds Entertainment', 'Turkey', 2005, 'https://www.taleworlds.com' WHERE NOT EXISTS (SELECT 1 FROM publishers WHERE name = 'TaleWorlds Entertainment');
INSERT INTO developers (name, country, website) SELECT 'Rockstar Games', 'USA', 'https://www.rockstargames.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Rockstar Games');
INSERT INTO developers (name, country, website) SELECT 'Game Science', 'China', 'https://www.heishenhua.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Game Science');
INSERT INTO developers (name, country, website) SELECT 'Team Cherry', 'Australia', 'https://www.teamcherry.com.au' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Team Cherry');
INSERT INTO developers (name, country, website) SELECT 'Sandfall Interactive', 'France', 'https://www.sandfall.co' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Sandfall Interactive');
INSERT INTO developers (name, country, website) SELECT 'Hazelight Studios', 'Sweden', 'https://www.hazelight.se' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Hazelight Studios');
INSERT INTO developers (name, country, website) SELECT 'Warhorse Studios', 'Czech Republic', 'https://warhorsestudios.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Warhorse Studios');
INSERT INTO developers (name, country, website) SELECT 'Capcom', 'Japan', 'https://www.capcom.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Capcom');
INSERT INTO developers (name, country, website) SELECT 'Playground Games', 'UK', 'https://playground-games.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Playground Games');
INSERT INTO developers (name, country, website) SELECT 'ConcernedApe', 'USA', 'https://www.stardewvalley.net' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'ConcernedApe');
INSERT INTO developers (name, country, website) SELECT 'Re-Logic', 'USA', 'https://terraria.org' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Re-Logic');
INSERT INTO developers (name, country, website) SELECT 'Pocketpair', 'Japan', 'https://www.pocketpair.jp' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'Pocketpair');
INSERT INTO developers (name, country, website) SELECT 'TaleWorlds Entertainment', 'Turkey', 'https://www.taleworlds.com' WHERE NOT EXISTS (SELECT 1 FROM developers WHERE name = 'TaleWorlds Entertainment');
INSERT INTO tags (name, description) VALUES ('Adventure', 'Exploration and journey-driven play') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Platformer', 'Jumping and movement challenges') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Horror', 'Tension, dread and survival against terrifying threats') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Survival', 'Gather, craft and stay alive') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Simulation', 'Life, farming and management systems') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, description) VALUES ('Strategy', 'Planning, command and tactics') ON CONFLICT (name) DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Red Dead Redemption 2', 'An outlaw and his gang run from the law across a vast American frontier in the last days of the Wild West.', '2019-12-05', 4999,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Rockstar Games'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Rockstar Games'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Red Dead Redemption 2');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Red Dead Redemption 2' AND t.name IN ('Action', 'Open World', 'Story Rich', 'Adventure')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Black Myth: Wukong', 'An action RPG rooted in Chinese mythology, built around demanding boss fights and shape-shifting combat.', '2024-08-20', 3599,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Game Science'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Game Science'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Black Myth: Wukong');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Black Myth: Wukong' AND t.name IN ('Action', 'RPG', 'Souls-like')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Hollow Knight: Silksong', 'Play as Hornet and climb through a haunted kingdom of silk and song in a fast, acrobatic action adventure.', '2025-09-04', 880,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Team Cherry'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Team Cherry'), 'Everyone 10+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Hollow Knight: Silksong');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Hollow Knight: Silksong' AND t.name IN ('Action', 'Indie', 'Platformer', 'Adventure')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Clair Obscur: Expedition 33', 'A turn-based RPG with real-time reactions, following an expedition sent to stop a being that erases people by painting a number.', '2025-04-24', 2999,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Kepler Interactive'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Sandfall Interactive'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Clair Obscur: Expedition 33');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Clair Obscur: Expedition 33' AND t.name IN ('RPG', 'Story Rich')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Split Fiction', 'Two writers are trapped inside their own stories in a co-op adventure that jumps between science fiction and fantasy.', '2025-03-06', 2499,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Electronic Arts'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Hazelight Studios'), 'Teen'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Split Fiction');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Split Fiction' AND t.name IN ('Action', 'Co-op', 'Adventure', 'Platformer')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Kingdom Come: Deliverance II', 'A grounded open-world RPG in 15th-century Bohemia, where a blacksmith''s son is drawn into war and intrigue.', '2025-02-04', 3360,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Deep Silver'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Warhorse Studios'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Kingdom Come: Deliverance II');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Kingdom Come: Deliverance II' AND t.name IN ('RPG', 'Open World', 'Story Rich')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Resident Evil Requiem', 'A survival horror entry that mixes tense investigation with close-quarters action.', '2026-02-27', 4399,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Capcom'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Capcom'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Resident Evil Requiem');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Resident Evil Requiem' AND t.name IN ('Action', 'Horror', 'Story Rich')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Forza Horizon 6', 'The Horizon festival arrives in Japan, with open roads from neon city streets to mountain passes.', '2026-05-19', 5499,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Xbox Game Studios'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Playground Games'), 'Everyone'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Forza Horizon 6');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Forza Horizon 6' AND t.name IN ('Racing', 'Open World')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Stardew Valley', 'Restore an old farm, grow crops, explore the mines and get to know a small town.', '2016-02-26', 479,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'ConcernedApe'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'ConcernedApe'), 'Everyone 10+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Stardew Valley');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Stardew Valley' AND t.name IN ('Indie', 'RPG', 'Simulation', 'Co-op')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Terraria', 'Dig, build and fight through a two-dimensional sandbox full of bosses, caves and crafting.', '2011-05-16', 480,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Re-Logic'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Re-Logic'), 'Teen'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Terraria');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Terraria' AND t.name IN ('Indie', 'Action', 'Survival', 'Co-op')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Palworld', 'Survive, build and explore alongside collectible creatures in an open world.', '2024-01-19', 1300,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'Pocketpair'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'Pocketpair'), 'Teen'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Palworld');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Palworld' AND t.name IN ('Open World', 'Survival', 'Co-op')
ON CONFLICT DO NOTHING;

INSERT INTO games (title, description, release_date, base_price, publisher_id, developer_id, age_rating)
SELECT 'Mount & Blade II: Bannerlord', 'Raise an army, trade, scheme and lead large medieval battles in a sandbox campaign.', '2022-10-25', 2499,
       (SELECT MIN(publisher_id) FROM publishers WHERE name = 'TaleWorlds Entertainment'),
       (SELECT MIN(developer_id) FROM developers WHERE name = 'TaleWorlds Entertainment'), 'Mature 17+'
WHERE NOT EXISTS (SELECT 1 FROM games WHERE title = 'Mount & Blade II: Bannerlord');
INSERT INTO game_tags (game_id, tag_id)
SELECT g.game_id, t.tag_id FROM games g CROSS JOIN tags t
WHERE g.title = 'Mount & Blade II: Bannerlord' AND t.name IN ('Action', 'RPG', 'Strategy', 'Open World')
ON CONFLICT DO NOTHING;

-- The Christmas sale replaces the autumn sale. Times are UTC: 26 Nov 00:00 to 31 Dec 23:59 IST.
UPDATE sales SET end_date = '2026-11-25 18:29:59'
WHERE title = 'Steam Autumn Sale 2026' AND end_date > '2026-11-25 18:29:59';
INSERT INTO sales (title, start_date, end_date)
VALUES ('SAUNA Early Christmas Sale 2026', '2026-11-25 18:30:00', '2026-12-31 18:29:59');
INSERT INTO sale_items (sale_id, game_id, discount_pct)
SELECT s.sale_id, g.game_id, d.pct
FROM (VALUES
    ('Half-Life: Alyx', 60),
    ('Portal 2', 80),
    ('Cyberpunk 2077', 55),
    ('The Witcher 3: Wild Hunt', 75),
    ('ELDEN RING', 35),
    ('Hades', 65),
    ('Hades II', 30),
    ('Hollow Knight', 50),
    ('Baldur''s Gate 3', 25),
    ('Forza Horizon 5', 60),
    ('Pentiment', 50),
    ('Red Dead Redemption 2', 70),
    ('Black Myth: Wukong', 30),
    ('Hollow Knight: Silksong', 20),
    ('Clair Obscur: Expedition 33', 25),
    ('Split Fiction', 40),
    ('Kingdom Come: Deliverance II', 50),
    ('Resident Evil Requiem', 25),
    ('Forza Horizon 6', 15),
    ('Stardew Valley', 40),
    ('Terraria', 50),
    ('Palworld', 30),
    ('Mount & Blade II: Bannerlord', 40)
) AS d(title, pct)
JOIN games g ON g.title = d.title
JOIN sales s ON s.title = 'SAUNA Early Christmas Sale 2026'
ON CONFLICT (sale_id, game_id) DO NOTHING;
