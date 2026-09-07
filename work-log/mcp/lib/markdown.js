/** ATX headings and fenced code share one parser in indexing and section reads. */
export function markdownLines(body) {
  let fence = null;
  return body.split('\n').map((text, line) => {
    const marker = text.replace(/\r$/, '').match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
    let code = fence !== null;
    if (fence) {
      if (marker && marker[1][0] === fence.char && marker[1].length >= fence.length && !marker[2].trim()) {
        fence = null;
      }
    } else if (marker && (marker[1][0] !== '`' || !marker[2].includes('`'))) {
      fence = { char: marker[1][0], length: marker[1].length };
      code = true;
    }
    const match = !code && text.match(/^ {0,3}(#{1,6})[ \t]+(.+?)\s*$/);
    const heading = match ? {
      level: match[1].length, title: match[2].replace(/[ \t]+#+[ \t]*$/, '').trim(),
    } : null;
    return { text, line, code, heading };
  });
}
