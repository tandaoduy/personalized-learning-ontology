import { copyFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const files = [
  ["node_modules/alpinejs/dist/cdn.min.js", "flask_app/static/vendor/js/alpine.min.js"],
  ["node_modules/htmx.org/dist/htmx.min.js", "flask_app/static/vendor/js/htmx.min.js"],
  ["node_modules/chart.js/dist/chart.umd.js", "flask_app/static/vendor/js/chart.umd.js"],
  ["node_modules/lucide/dist/umd/lucide.js", "flask_app/static/vendor/js/lucide.js"],
  ["node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2", "flask_app/static/vendor/fonts/inter-var.woff2"]
];

for (const [source, target] of files) {
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}

console.log(`Copied ${files.length} UI vendor assets.`);
