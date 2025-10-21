cp -u -r "$(dirname "$0")/vitepress" ~/
cd ~/vitepress
pnpm run docs:build
rm -rf "$(dirname "$0")"/assets
cp -r ~/vitepress/docs/.vitepress/dist/* "$(dirname "$0")"/
cd "$(dirname "$0")"
