CREATE INDEX `idx_experiments_created_at` ON `experiments` (`created_at`);--> statement-breakpoint
CREATE INDEX `idx_signals_created_at` ON `signals` (`created_at`);--> statement-breakpoint
CREATE INDEX `idx_trades_opened_at` ON `trades` (`opened_at`);--> statement-breakpoint
PRAGMA optimize;
