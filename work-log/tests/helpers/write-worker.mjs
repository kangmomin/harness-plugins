import fsp from 'node:fs/promises';
import { writeDoc } from '../../mcp/lib/vault.js';

// 느린 파일 읽기를 재현해 두 프로세스의 충돌 구간을 안정적으로 겹친다.
const readFile = fsp.readFile;
fsp.readFile = async (...args) => {
  const value = await readFile(...args);
  if (String(args[0]).endsWith('/doc.md')) await new Promise((resolve) => setTimeout(resolve, 30));
  return value;
};
process.on('message', async ({ cfg, args }) => {
  try { process.send({ ok: true, result: await writeDoc(cfg, args) }); }
  catch (error) { process.send({ ok: false, error: error.message }); }
});
process.send({ ready: true });
