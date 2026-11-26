-- Seed data for Steam Store & Gaming Platform (steam_db)
USE steam_db;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE GAME_TAGS;
TRUNCATE TABLE TAGS;
TRUNCATE TABLE USER_ACHIEVEMENTS;
TRUNCATE TABLE ACHIEVEMENTS;
TRUNCATE TABLE SALE_ITEMS;
TRUNCATE TABLE SALES;
TRUNCATE TABLE WISHLIST;
TRUNCATE TABLE REVIEWS;
TRUNCATE TABLE USER_LIBRARY;
TRUNCATE TABLE ORDER_ITEMS;
TRUNCATE TABLE WALLET_TRANSACTIONS;
TRUNCATE TABLE ORDERS;
TRUNCATE TABLE FRIENDSHIPS;
TRUNCATE TABLE USERS;
TRUNCATE TABLE GAMES;
TRUNCATE TABLE DEVELOPERS;
TRUNCATE TABLE PUBLISHERS;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. PUBLISHERS
INSERT INTO PUBLISHERS (publisher_id, name, country, founded_year, website) VALUES
(1, 'Valve Corporation', 'USA', 1996, 'https://www.valvesoftware.com'),
(2, 'CD PROJEKT RED', 'Poland', 2002, 'https://www.cdprojektred.com'),
(3, 'Bandai Namco Entertainment', 'Japan', 1955, 'https://www.bandainamcoent.com'),
(4, 'Supergiant Games', 'USA', 2009, 'https://www.supergiantgames.com'),
(5, 'Team Cherry', 'Australia', 2014, 'https://www.teamcherry.com.au'),
(6, 'Larian Studios', 'Belgium', 1996, 'https://larian.com'),
(7, 'Xbox Game Studios', 'USA', 2000, 'https://www.xbox.com/xbox-game-studios');

-- 2. DEVELOPERS
INSERT INTO DEVELOPERS (developer_id, name, country, website) VALUES
(1, 'Valve', 'USA', 'https://www.valvesoftware.com'),
(2, 'CD PROJEKT RED', 'Poland', 'https://www.cdprojektred.com'),
(3, 'FromSoftware', 'Japan', 'https://www.fromsoftware.jp'),
(4, 'Supergiant Games', 'USA', 'https://www.supergiantgames.com'),
(5, 'Team Cherry', 'Australia', 'https://www.teamcherry.com.au'),
(6, 'Larian Studios', 'Belgium', 'https://larian.com'),
(7, 'Playground Games', 'UK', 'https://playground-games.com'),
(8, 'Obsidian Entertainment', 'USA', 'https://www.obsidian.net');

-- 3. GAMES
INSERT INTO GAMES (game_id, title, description, release_date, base_price, publisher_id, developer_id, age_rating) VALUES
(1, 'Counter-Strike 2', 'For over two decades, Counter-Strike has offered an elite competitive experience, built on Source 2 engine with upgraded maps and tactical teamplay.', '2023-09-27', 0.00, 1, 1, 'Mature 17+'),
(2, 'Half-Life: Alyx', 'Valve''s VR return to the Half-Life series. Set between Half-Life and Half-Life 2, fight against the Combine as Alyx Vance.', '2020-03-23', 59.99, 1, 1, 'Mature 17+'),
(3, 'Portal 2', 'The perpetual testing initiative continues with mind-bending co-op and single-player portal puzzles powered by GLaDOS.', '2011-04-19', 9.99, 1, 1, 'Everyone 10+'),
(4, 'Cyberpunk 2077', 'An open-world, action-adventure RPG set in Night City, a megalopolis obsessed with power, glamour, and body modification.', '2020-12-10', 59.99, 2, 2, 'Mature 17+'),
(5, 'The Witcher 3: Wild Hunt', 'You are Geralt of Rivia, mercenary monster slayer. Explore a war-torn continent and track down Ciri, the Child of Prophecy.', '2015-05-19', 39.99, 2, 2, 'Mature 17+'),
(6, 'ELDEN RING', 'Rise, Tarnished, and be guided by grace to brandish the power of the Elden Ring and become an Elden Lord in the Lands Between.', '2022-02-25', 59.99, 3, 3, 'Mature 17+'),
(7, 'Hades', 'Defy the god of the dead as you hack and slash out of the Underworld in this rogue-like dungeon crawler from Supergiant Games.', '2020-09-17', 24.99, 4, 4, 'Teen'),
(8, 'Hades II', 'Battle beyond the Underworld using dark sorcery to take on the Titan of Time in Supergiant''s bewitching sequel.', '2025-09-25', 29.99, 4, 4, 'Teen'),
(9, 'Hollow Knight', 'Forge your own path in Hollow Knight! An epic action adventure through a vast ruined kingdom of insects and heroes.', '2017-02-24', 14.99, 5, 5, 'Everyone 10+'),
(10, 'Baldur''s Gate 3', 'Gather your party and return to the Forgotten Realms in a tale of fellowship and betrayal, sacrifice and survival.', '2023-08-03', 59.99, 6, 6, 'Mature 17+'),
(11, 'Forza Horizon 5', 'Your Ultimate Horizon Adventure awaits! Explore the vibrant open world landscapes of Mexico with limitless driving action.', '2021-11-09', 59.99, 7, 7, 'Everyone'),
(12, 'Pentiment', 'Step into a living illustrated world in 16th-century Bavaria and unravel a series of murders spanning twenty-five years.', '2022-11-15', 19.99, 7, 8, 'Mature 17+');

-- 4. USERS (default seeded password for all demo accounts: password123)
INSERT INTO USERS (user_id, username, email, password_hash, wallet_balance, country, created_at) VALUES
(1, 'arjun_dev', 'arjun@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 145.50, 'India', '2023-01-15 10:22:00'),
(2, 'elena_vance', 'elena@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 82.00, 'USA', '2022-06-03 14:10:00'),
(3, 'kenji_k', 'kenji@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 210.25, 'Japan', '2021-11-20 08:45:00'),
(4, 'marta_r', 'marta@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 35.00, 'Poland', '2024-02-11 19:30:00'),
(5, 'liam_os', 'liam@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 50.00, 'UK', '2024-08-09 12:05:00'),
(6, 'sara_chen', 'sara@ferroy.io', 'scrypt:32768:8:1$6GOOMpmt2bBr3BM0$f5b262259419bcf308acf497fb17d7c4a2c9fe292aa3aac8edd8bfc82c9eac12b191b6e043621297298f22e47021fbff86d62819d2227e3215b42554bbcafaa2', 120.00, 'Canada', '2025-01-04 16:40:00');

-- 5. FRIENDSHIPS
INSERT INTO FRIENDSHIPS (user_id, friend_id, status, created_at) VALUES
(1, 2, 'accepted', '2023-04-10 11:00:00'),
(1, 3, 'accepted', '2023-07-22 18:30:00'),
(1, 4, 'pending', '2026-11-20 09:15:00'),
(2, 3, 'accepted', '2022-12-01 20:00:00'),
(2, 5, 'accepted', '2024-09-14 15:20:00'),
(3, 6, 'accepted', '2025-03-08 07:55:00'),
(5, 1, 'pending', '2026-11-24 21:10:00');

-- 6. ORDERS
INSERT INTO ORDERS (order_id, user_id, total_amount, payment_method, status, created_at) VALUES
(1, 1, 84.98, 'Steam Wallet', 'completed', '2025-11-25 14:20:00'),
(2, 1, 14.99, 'UPI', 'completed', '2026-03-12 19:05:00'),
(3, 2, 79.98, 'Credit Card', 'completed', '2025-07-02 10:40:00'),
(4, 3, 119.98, 'Steam Wallet', 'completed', '2026-01-19 22:15:00'),
(5, 4, 29.99, 'Steam Wallet', 'completed', '2026-06-28 16:00:00'),
(6, 5, 24.99, 'PayPal', 'completed', '2026-10-05 11:30:00'),
(7, 6, 47.99, 'Steam Wallet', 'completed', '2026-11-22 13:45:00');

-- 7. WALLET_TRANSACTIONS
INSERT INTO WALLET_TRANSACTIONS (txn_id, user_id, amount, txn_type, reference_order_id, created_at) VALUES
(1, 1, 200.00, 'deposit', NULL, '2025-11-20 09:00:00'),
(2, 1, -84.98, 'purchase', 1, '2025-11-25 14:20:00'),
(3, 1, 30.48, 'deposit', NULL, '2026-05-01 12:00:00'),
(4, 2, 82.00, 'deposit', NULL, '2025-06-15 08:30:00'),
(5, 3, 330.23, 'deposit', NULL, '2026-01-10 17:00:00'),
(6, 3, -119.98, 'purchase', 4, '2026-01-19 22:15:00'),
(7, 4, 64.99, 'deposit', NULL, '2026-06-20 11:10:00'),
(8, 4, -29.99, 'purchase', 5, '2026-06-28 16:00:00'),
(9, 5, 50.00, 'deposit', NULL, '2026-09-01 15:00:00'),
(10, 6, 167.99, 'deposit', NULL, '2026-11-18 10:00:00'),
(11, 6, -47.99, 'purchase', 7, '2026-11-22 13:45:00');

-- 8. ORDER_ITEMS
INSERT INTO ORDER_ITEMS (order_item_id, order_id, game_id, price_at_purchase) VALUES
(1, 1, 6, 59.99),
(2, 1, 7, 24.99),
(3, 2, 9, 14.99),
(4, 3, 5, 19.99),
(5, 3, 2, 59.99),
(6, 4, 10, 59.99),
(7, 4, 4, 59.99),
(8, 5, 5, 19.99),
(9, 5, 3, 9.99),
(10, 6, 7, 24.99),
(11, 7, 10, 47.99);

-- 9. USER_LIBRARY
INSERT INTO USER_LIBRARY (user_id, game_id, acquired_at, playtime_minutes, last_played_at) VALUES
(1, 1, '2023-10-01 18:00:00', 4820, '2026-11-25 22:15:00'),
(1, 6, '2025-11-25 14:20:00', 3140, '2026-11-21 20:00:00'),
(1, 7, '2025-11-25 14:20:00', 1450, '2026-10-14 19:30:00'),
(1, 9, '2026-03-12 19:05:00', 980, '2026-11-02 15:10:00'),
(2, 1, '2023-09-29 12:00:00', 1200, '2026-08-19 21:00:00'),
(2, 2, '2025-07-02 10:40:00', 760, '2026-04-12 17:45:00'),
(2, 5, '2025-07-02 10:40:00', 5400, '2026-11-18 23:00:00'),
(3, 4, '2026-01-19 22:15:00', 2210, '2026-11-24 19:00:00'),
(3, 10, '2026-01-19 22:15:00', 6180, '2026-11-25 23:50:00'),
(4, 3, '2026-06-28 16:00:00', 510, '2026-07-15 14:00:00'),
(4, 5, '2026-06-28 16:00:00', 3890, '2026-11-20 18:30:00'),
(5, 7, '2026-10-05 11:30:00', 640, '2026-11-19 20:45:00'),
(6, 10, '2026-11-22 13:45:00', 420, '2026-11-25 21:20:00');

-- 10. REVIEWS
INSERT INTO REVIEWS (review_id, user_id, game_id, is_recommended, review_text, playtime_at_review, helpful_votes, created_at) VALUES
(1, 1, 6, TRUE, 'An unforgettable open-world masterpiece. Every corner hides a new boss or secret dungeon.', 2800, 42, '2026-02-10 15:20:00'),
(2, 1, 7, TRUE, 'Tight combat, stellar voice acting, and an addictive loop that keeps pulling you back.', 1200, 19, '2026-04-03 11:10:00'),
(3, 1, 9, TRUE, 'Hand-crafted atmospheric perfection. The soundtrack and boss fights are top tier.', 900, 27, '2026-06-14 19:45:00'),
(4, 2, 5, TRUE, 'Still the gold standard for narrative-driven RPGs. Blood and Wine alone feels like a full game.', 4900, 88, '2026-01-22 17:00:00'),
(5, 2, 2, TRUE, 'VR immersion unlike anything else. Chapter 7 is peak gaming tension.', 720, 35, '2026-03-30 20:15:00'),
(6, 3, 10, TRUE, 'Unmatched player agency and companion writing. Every playthrough reveals brand-new outcomes.', 4500, 114, '2026-07-11 09:30:00'),
(7, 3, 4, TRUE, 'Night City looks breathtaking after the major updates and Phantom Liberty.', 1900, 31, '2026-08-05 22:00:00'),
(8, 4, 3, TRUE, 'Hilarious writing and brilliant co-op puzzles that still hold up over a decade later.', 500, 16, '2026-07-20 13:20:00'),
(9, 1, 1, FALSE, 'Great gunplay as always, though matchmaking still needs better anti-cheat coverage.', 4600, 12, '2026-10-18 21:40:00');

-- 11. WISHLIST
INSERT INTO WISHLIST (user_id, game_id, added_at) VALUES
(1, 8, '2026-09-26 10:00:00'),
(1, 10, '2026-10-12 18:20:00'),
(1, 4, '2026-11-01 09:45:00'),
(2, 6, '2026-05-14 14:10:00'),
(2, 12, '2026-08-22 16:30:00'),
(3, 8, '2026-10-02 20:00:00'),
(4, 6, '2026-11-15 12:00:00'),
(5, 11, '2026-11-10 17:50:00');

-- 12. SALES
INSERT INTO SALES (sale_id, title, start_date, end_date) VALUES
(1, 'Steam Summer Sale 2026', '2026-06-25 17:00:00', '2026-07-09 17:00:00'),
(2, 'Steam Autumn Sale 2026', '2026-11-20 00:00:00', '2026-12-05 23:59:59'),
(3, 'Steam Winter Sale 2026', '2026-12-18 18:00:00', '2027-01-04 18:00:00');

-- 13. SALE_ITEMS
INSERT INTO SALE_ITEMS (sale_id, game_id, discount_pct) VALUES
(1, 5, 75),
(1, 9, 50),
(2, 4, 50),
(2, 5, 75),
(2, 6, 30),
(2, 7, 60),
(2, 9, 50),
(2, 10, 20),
(2, 11, 50),
(2, 12, 40),
(3, 2, 66),
(3, 8, 25);

-- 14. ACHIEVEMENTS
INSERT INTO ACHIEVEMENTS (achievement_id, game_id, name, description, is_hidden) VALUES
(1, 6, 'Elden Lord', 'Achieved the "Elden Lord" ending.', FALSE),
(2, 6, 'Shardbearer Malenia', 'Defeated Shardbearer Malenia, Blade of Miquella.', TRUE),
(3, 6, 'Roundtable Hold', 'Arrived at Roundtable Hold.', FALSE),
(4, 7, 'Is There No Escape?', 'Cleared an escape attempt from the Underworld.', FALSE),
(5, 7, 'Friends Forever', 'Maxed out keepsake bonds with Chthonic allies.', TRUE),
(6, 9, 'Falsehood', 'Defeat the False Knight in Forgotten Crossroads.', FALSE),
(7, 9, 'Dream No More', 'Defeat the Radiance and consume the light.', TRUE),
(8, 5, 'Lilac and Gooseberries', 'Find Yennefer of Vengerberg.', FALSE),
(9, 10, 'Hero of the Forgotten Realms', 'Save Baldur''s Gate from the Absolute.', TRUE),
(10, 4, 'The Fool', 'Become a mercenary in Night City.', FALSE),
(11, 3, 'Wake Up Call', 'Survive the manual override.', FALSE),
(12, 1, 'A New Beginning', 'Win 10 Competitive matches.', FALSE);

-- 15. USER_ACHIEVEMENTS
INSERT INTO USER_ACHIEVEMENTS (user_id, achievement_id, unlocked_at) VALUES
(1, 3, '2025-11-25 16:10:00'),
(1, 1, '2026-01-14 21:45:00'),
(1, 2, '2026-01-29 23:12:00'),
(1, 4, '2025-12-09 19:30:00'),
(1, 6, '2026-03-13 18:00:00'),
(2, 8, '2025-07-03 14:20:00'),
(3, 10, '2026-01-20 12:15:00'),
(3, 9, '2026-06-05 22:40:00'),
(4, 11, '2026-06-29 15:05:00'),
(4, 8, '2026-07-01 11:30:00');

-- 16. TAGS
INSERT INTO TAGS (tag_id, name, description) VALUES
(1, 'RPG', 'Role-playing games with character progression and deep stories'),
(2, 'Action', 'Fast-paced combat, reflexes, and kinetic gameplay'),
(3, 'Open World', 'Expansive non-linear environments to explore freely'),
(4, 'Indie', 'Developed by independent studios with creative vision'),
(5, 'Souls-like', 'Challenging combat, intricate world design, and rewarding mastery'),
(6, 'Roguelike', 'Procedural runs, permanent stakes, and build variety'),
(7, 'FPS', 'First-person shooter tactical and arena gameplay'),
(8, 'Co-op', 'Cooperative multiplayer experiences with friends'),
(9, 'Story Rich', 'Narrative-driven games with memorable characters'),
(10, 'Racing', 'High-speed motorsport and open-road driving');

-- 17. GAME_TAGS
INSERT INTO GAME_TAGS (game_id, tag_id) VALUES
(1, 2), (1, 7), (1, 8),
(2, 2), (2, 7), (2, 9),
(3, 8), (3, 9),
(4, 1), (4, 2), (4, 3), (4, 9),
(5, 1), (5, 3), (5, 9),
(6, 1), (6, 2), (6, 3), (6, 5),
(7, 2), (7, 4), (7, 6), (7, 9),
(8, 2), (8, 4), (8, 6), (8, 9),
(9, 2), (9, 4), (9, 5),
(10, 1), (10, 8), (10, 9),
(11, 3), (11, 10),
(12, 1), (12, 4), (12, 9);

-- Reset auto_increment counters cleanly
ALTER TABLE PUBLISHERS AUTO_INCREMENT = 8;
ALTER TABLE DEVELOPERS AUTO_INCREMENT = 9;
ALTER TABLE GAMES AUTO_INCREMENT = 13;
ALTER TABLE USERS AUTO_INCREMENT = 7;
ALTER TABLE ORDERS AUTO_INCREMENT = 8;
ALTER TABLE WALLET_TRANSACTIONS AUTO_INCREMENT = 12;
ALTER TABLE ORDER_ITEMS AUTO_INCREMENT = 12;
ALTER TABLE REVIEWS AUTO_INCREMENT = 10;
ALTER TABLE SALES AUTO_INCREMENT = 4;
ALTER TABLE ACHIEVEMENTS AUTO_INCREMENT = 13;
ALTER TABLE TAGS AUTO_INCREMENT = 11;
