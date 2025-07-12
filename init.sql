create table if not exists algabot (
	chat_id INT UNIQUE,
	card_number TEXT,
	threshold REAL
);
