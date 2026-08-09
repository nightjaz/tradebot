import { sql } from "drizzle-orm";
import { index, integer, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const engineState = sqliteTable("engine_state", {
  id: integer("id").primaryKey(),
  armed: integer("armed", { mode: "boolean" }).notNull().default(false),
  mode: text("mode").notNull().default("paper"),
  capital: real("capital").notNull().default(20000),
  realisedPnl: real("realised_pnl").notNull().default(0),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const signals = sqliteTable("signals", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  symbol: text("symbol").notNull(), side: text("side").notNull(),
  score: real("score").notNull(), thesis: text("thesis").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [index("idx_signals_created_at").on(table.createdAt)]);

export const trades = sqliteTable("trades", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  symbol: text("symbol").notNull(), side: text("side").notNull(), quantity: integer("quantity").notNull(),
  entry: real("entry").notNull(), exit: real("exit"), costs: real("costs").notNull().default(0),
  realisedPnl: real("realised_pnl"), status: text("status").notNull().default("open"),
  openedAt: text("opened_at").notNull().default(sql`CURRENT_TIMESTAMP`), closedAt: text("closed_at"),
}, (table) => [index("idx_trades_opened_at").on(table.openedAt)]);

export const experiments = sqliteTable("experiments", {
  id: integer("id").primaryKey({ autoIncrement: true }), name: text("name").notNull().unique(),
  role: text("role").notNull(), returnPct: real("return_pct").notNull().default(0),
  maxDrawdownPct: real("max_drawdown_pct").notNull().default(0), configJson: text("config_json").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [index("idx_experiments_created_at").on(table.createdAt)]);
