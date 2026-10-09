/** Keep isolated verification servers from sharing development build output. */
export default { distDir: process.env.NEXT_DIST_DIR || '.next' };
