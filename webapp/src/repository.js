// Public deployment settings. Vite embeds these values in the browser bundle;
// credentials must never be supplied through VITE_* variables.
export const REPOSITORY = import.meta.env.VITE_GITHUB_REPOSITORY || 'Stawberrymind/flood_river_watch';
export const BRANCH = import.meta.env.VITE_GITHUB_BRANCH || 'master';
export const REPO = `https://github.com/${REPOSITORY}`;
export const RAW = `https://raw.githubusercontent.com/${REPOSITORY}/${BRANCH}/`;
