/**
 * Next.js configuration.
 *
 * The dev server runs on **3100**, set in `package.json` rather than here — 3000 through
 * 3003 are all occupied on the development machine, checked rather than assumed, so the
 * Next.js default would have collided on day one.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The chat path streams, so nothing on it may be statically optimised or cached.
  // `useTurn` guards against the double-mount that strict mode causes in development.
  experimental: {},
  // Overridable so a production build can be verified while the dev server holds `.next`.
  // Building into a live `.next` corrupts the running server — a trap this repo has hit.
  //   NEXT_DIST_DIR=.next-verify npx next build
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
