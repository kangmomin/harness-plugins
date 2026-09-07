import { ioTransaction } from '../../mcp/lib/io.js';
import { buildIndex, indexPaths } from '../../mcp/lib/vault.js';

let release;
process.on('message', async (message) => {
  if (message.type === 'release') return release?.();
  try {
    const { dir } = indexPaths(message.cfg.root);
    await ioTransaction({ operation: 'index', root: dir, relPath: 'index.json' }, async () => {
      const index = buildIndex(message.cfg);
      process.send({ type: 'before-commit' });
      await new Promise((resolve) => { release = resolve; });
      return { content: JSON.stringify(index) };
    });
    process.send({ type: 'done' });
  } catch (error) {
    process.send({ type: 'error', message: error.message });
  }
});
process.send({ type: 'ready' });
