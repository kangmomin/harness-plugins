import { writeDoc } from '../../mcp/lib/vault.js';

process.on('message', async ({ cfg, args }) => {
  try { process.send({ ok: true, result: await writeDoc(cfg, args) }); }
  catch (error) { process.send({ ok: false, error: error.message }); }
});
process.send({ ready: true });
