import { readFile, writeFile, mkdir } from 'node:fs/promises';
const source = new URL('./src/t2c_clermont-ferrand_card.js', import.meta.url);
const output = new URL('../custom_components/t2c_clermontferrand/www/t2c_clermont-ferrand_card.js', import.meta.url);
const content = await readFile(source);
if (process.argv.includes('--check')) {
  if (!content.equals(await readFile(output))) throw new Error('Bundled card is stale. Run npm run build in frontend/.');
} else {
  await mkdir(new URL('.', output), { recursive: true });
  await writeFile(output, content);
}
