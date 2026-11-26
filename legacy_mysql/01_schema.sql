-- Steam Store & Gaming Platform Database Schema
-- Generated directly from steam_er_diagram.png (17 entities)

CREATE DATABASE IF NOT EXISTS steam_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE steam_db;

-- 1. PUBLISHERS
CREATE TABLE IF NOT EXISTS PUBLISHERS (
    publisher_id INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    country      VARCHAR(100),
    founded_year INT,
    website      VARCHAR(255)
) ENGINE=InnoDB;

-- 2. DEVELOPERS
CREATE TABLE IF NOT EXISTS DEVELOPERS (
    developer_id INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    country      VARCHAR(100),
    website      VARCHAR(255)
) ENGINE=InnoDB;

-- 3. GAMES
CREATE TABLE IF NOT EXISTS GAMES (
    game_id      INT AUTO_INCREMENT PRIMARY KEY,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    release_date DATE,
    base_price   DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    publisher_id INT NOT NULL,
    developer_id INT NOT NULL,
    age_rating   VARCHAR(50),
    CONSTRAINT fk_games_publisher
        FOREIGN KEY (publisher_id) REFERENCES PUBLISHERS(publisher_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_games_developer
        FOREIGN KEY (developer_id) REFERENCES DEVELOPERS(developer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_games_base_price CHECK (base_price >= 0),
    INDEX idx_games_title (title),
    INDEX idx_games_publisher (publisher_id),
    INDEX idx_games_developer (developer_id)
) ENGINE=InnoDB;

-- 4. USERS
CREATE TABLE IF NOT EXISTS USERS (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    username       VARCHAR(100) NOT NULL UNIQUE,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    wallet_balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    country        VARCHAR(100),
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_users_wallet CHECK (wallet_balance >= 0)
) ENGINE=InnoDB;

-- 5. FRIENDSHIPS
CREATE TABLE IF NOT EXISTS FRIENDSHIPS (
    user_id    INT NOT NULL,
    friend_id  INT NOT NULL,
    status     VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, friend_id),
    CONSTRAINT fk_friendships_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_friendships_friend
        FOREIGN KEY (friend_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

DROP TRIGGER IF EXISTS trg_friendships_no_self;
DELIMITER //
CREATE TRIGGER trg_friendships_no_self
BEFORE INSERT ON FRIENDSHIPS
FOR EACH ROW
BEGIN
    IF NEW.user_id = NEW.friend_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A user cannot add themselves as a friend';
    END IF;
END//
DELIMITER ;

-- 6. ORDERS
CREATE TABLE IF NOT EXISTS ORDERS (
    order_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    total_amount   DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status         VARCHAR(50) NOT NULL DEFAULT 'completed',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_orders_total CHECK (total_amount >= 0),
    INDEX idx_orders_user (user_id)
) ENGINE=InnoDB;

-- 7. WALLET_TRANSACTIONS
CREATE TABLE IF NOT EXISTS WALLET_TRANSACTIONS (
    txn_id             INT AUTO_INCREMENT PRIMARY KEY,
    user_id            INT NOT NULL,
    amount             DECIMAL(10, 2) NOT NULL,
    txn_type           VARCHAR(50) NOT NULL,
    reference_order_id INT NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wallet_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_wallet_order
        FOREIGN KEY (reference_order_id) REFERENCES ORDERS(order_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_wallet_user (user_id)
) ENGINE=InnoDB;

-- 8. ORDER_ITEMS
CREATE TABLE IF NOT EXISTS ORDER_ITEMS (
    order_item_id     INT AUTO_INCREMENT PRIMARY KEY,
    order_id          INT NOT NULL,
    game_id           INT NOT NULL,
    price_at_purchase DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES ORDERS(order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_order_items_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_order_item_price CHECK (price_at_purchase >= 0),
    UNIQUE KEY uq_order_game (order_id, game_id)
) ENGINE=InnoDB;

-- 9. USER_LIBRARY
CREATE TABLE IF NOT EXISTS USER_LIBRARY (
    user_id          INT NOT NULL,
    game_id          INT NOT NULL,
    acquired_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    playtime_minutes INT NOT NULL DEFAULT 0,
    last_played_at   DATETIME NULL,
    PRIMARY KEY (user_id, game_id),
    CONSTRAINT fk_library_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_library_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_library_playtime CHECK (playtime_minutes >= 0)
) ENGINE=InnoDB;

-- 10. REVIEWS
CREATE TABLE IF NOT EXISTS REVIEWS (
    review_id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id            INT NOT NULL,
    game_id            INT NOT NULL,
    is_recommended     BOOLEAN NOT NULL,
    review_text        TEXT,
    playtime_at_review INT NOT NULL DEFAULT 0,
    helpful_votes      INT NOT NULL DEFAULT 0,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_reviews_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE KEY uq_review_user_game (user_id, game_id),
    INDEX idx_reviews_game (game_id)
) ENGINE=InnoDB;

-- 11. WISHLIST
CREATE TABLE IF NOT EXISTS WISHLIST (
    user_id  INT NOT NULL,
    game_id  INT NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, game_id),
    CONSTRAINT fk_wishlist_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_wishlist_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- 12. SALES
CREATE TABLE IF NOT EXISTS SALES (
    sale_id    INT AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(255) NOT NULL,
    start_date DATETIME NOT NULL,
    end_date   DATETIME NOT NULL,
    CONSTRAINT chk_sales_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB;

-- 13. SALE_ITEMS
CREATE TABLE IF NOT EXISTS SALE_ITEMS (
    sale_id      INT NOT NULL,
    game_id      INT NOT NULL,
    discount_pct INT NOT NULL,
    PRIMARY KEY (sale_id, game_id),
    CONSTRAINT fk_sale_items_sale
        FOREIGN KEY (sale_id) REFERENCES SALES(sale_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_sale_items_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_sale_discount CHECK (discount_pct BETWEEN 1 AND 100)
) ENGINE=InnoDB;

-- 14. ACHIEVEMENTS
CREATE TABLE IF NOT EXISTS ACHIEVEMENTS (
    achievement_id INT AUTO_INCREMENT PRIMARY KEY,
    game_id        INT NOT NULL,
    name           VARCHAR(255) NOT NULL,
    description    TEXT,
    is_hidden      BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_achievements_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_achievements_game (game_id)
) ENGINE=InnoDB;

-- 15. USER_ACHIEVEMENTS
CREATE TABLE IF NOT EXISTS USER_ACHIEVEMENTS (
    user_id        INT NOT NULL,
    achievement_id INT NOT NULL,
    unlocked_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id),
    CONSTRAINT fk_user_ach_user
        FOREIGN KEY (user_id) REFERENCES USERS(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_user_ach_achievement
        FOREIGN KEY (achievement_id) REFERENCES ACHIEVEMENTS(achievement_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- 16. TAGS
CREATE TABLE IF NOT EXISTS TAGS (
    tag_id      INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
) ENGINE=InnoDB;

-- 17. GAME_TAGS
CREATE TABLE IF NOT EXISTS GAME_TAGS (
    game_id INT NOT NULL,
    tag_id  INT NOT NULL,
    PRIMARY KEY (game_id, tag_id),
    CONSTRAINT fk_game_tags_game
        FOREIGN KEY (game_id) REFERENCES GAMES(game_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_game_tags_tag
        FOREIGN KEY (tag_id) REFERENCES TAGS(tag_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;
