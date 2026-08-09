import { desc, eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { engineState, experiments, signals, trades } from "../../../db/schema";

const unavailable=(error:unknown)=>Response.json({error:error instanceof Error?error.message:"database unavailable"},{status:503});

export async function GET(){try{const db=getDb();const[state,recentSignals,recentTrades,variants]=await Promise.all([
 db.select().from(engineState).where(eq(engineState.id,1)).limit(1),
 db.select().from(signals).orderBy(desc(signals.createdAt)).limit(20),
 db.select().from(trades).orderBy(desc(trades.openedAt)).limit(20),
 db.select().from(experiments).orderBy(desc(experiments.createdAt)).limit(10),
]);return Response.json({state:state[0]??{id:1,armed:false,mode:"paper",capital:20000,realisedPnl:0},signals:recentSignals,trades:recentTrades,experiments:variants});}catch(e){return unavailable(e)}}

export async function POST(request:Request){try{const body=await request.json() as {armed?:boolean};if(typeof body.armed!=="boolean")return Response.json({error:"armed must be boolean"},{status:400});const db=getDb();await db.insert(engineState).values({id:1,armed:body.armed}).onConflictDoUpdate({target:engineState.id,set:{armed:body.armed,updatedAt:new Date().toISOString()}});return Response.json({armed:body.armed,mode:"paper"});}catch(e){return unavailable(e)}}
