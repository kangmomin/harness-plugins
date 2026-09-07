/** Python owns descriptors/locks/cleanup; JS supplies only the transformed text. */
import { spawn, spawnSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

const argv = ['-I', '-B', '-X', 'utf8', fileURLToPath(new URL('./io_worker.py', import.meta.url))];

export function ioCapability() {
  const result = spawnSync('python3', [...argv, '--probe'], { encoding: 'utf8', timeout: 3000 });
  try {
    const parsed = JSON.parse(result.stdout);
    if (parsed.available) return parsed;
    return { available: false, reason: parsed.message };
  } catch {
    return { available: false, reason: result.error?.message || result.stderr || 'Python >=3.9 with POSIX descriptor APIs required' };
  }
}

export async function ioTransaction(request, transform) {
  const child = spawn('python3', argv, { stdio: ['pipe', 'pipe', 'pipe'] });
  let failure, done, value, sentCommit = false, stderr = '';
  child.stderr.on('data', (data) => { stderr = (stderr + data).slice(-4096); });
  child.stdin.on('error', (error) => { failure ??= error; });
  const closed = new Promise((resolve) => {
    child.on('error', (error) => { failure = error; });
    child.on('close', resolve);
  });
  const send = (message) => child.stdin.write(JSON.stringify(message) + '\n');
  send(request);
  try {
    for await (const line of createInterface({ input: child.stdout, crlfDelay: Infinity })) {
      const message = JSON.parse(line);
      if (message.type === 'error') throw Object.assign(new Error(message.message), { writeState: message.writeState });
      if (message.type === 'read') {
        const transformed = await transform(message.existing, message.rel);
        value = transformed.value;
        send({ content: transformed.content });
      } else if (message.type === 'prepared') {
        sentCommit = true;
        send({ commit: true });
      } else if (message.type === 'done') {
        done = message;
        child.stdin.end();
      }
    }
  } catch (error) {
    failure = error;
    child.stdin.end(); // EOF aborts and releases locks through the helper's finally.
  }
  const code = await closed;
  if (!done) {
    const error = failure || new Error(`safe I/O helper exited (${code}): ${stderr}`);
    error.writeState ??= sentCommit ? 'unknown' : 'not_written';
    if (error.writeState === 'unknown') error.message += '; write_state=unknown: read the document before retrying append';
    throw error;
  }
  return { value, durability: done.durability, cleanupWarnings: done.cleanupWarnings };
}
