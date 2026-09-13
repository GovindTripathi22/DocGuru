import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    lockDistDir: false,
  },
};

export default nextConfig;
