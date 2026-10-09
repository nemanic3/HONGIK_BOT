import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2]);
function inspect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (/^(media|transcripts|\.git|\.env|secrets|backups)$/.test(entry.name)) throw new Error(`Private directory in assets: ${entry.name}`);
      inspect(file);
    } else if (/\.(sqlite3?|db|pdf|pem|key|dump|tar|gz)$/i.test(entry.name) || entry.name.startsWith('.env')) {
      throw new Error(`Private file type in assets: ${entry.name}`);
    }
  }
}
inspect(root);
for (const required of ['index.html', 'review.html', 'upload.html', 'mypage.html', '_routes.json', '_headers', '_redirects']) {
  if (!fs.existsSync(path.join(root, required))) throw new Error(`Missing exported asset: ${required}`);
}
console.log('Static export verified: routes present; no databases, PDFs, media directories, or secrets.');
